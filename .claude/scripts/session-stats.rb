#!/usr/bin/env ruby
# frozen_string_literal: true

# Session Statistics Calculator
# 從 Claude Code session jsonl 檔案中計算 tool 使用次數和 token 消耗
#
# Usage:
#   ruby session-stats.rb <session_id> [--since <ISO8601_timestamp>] [--task <task_id>]
#
# Examples:
#   ruby session-stats.rb 2debd0eb-a474-4abf-bb63-8575bc52a52a
#   ruby session-stats.rb 2debd0eb-a474-4abf-bb63-8575bc52a52a --since 2026-02-05T22:00:00+08:00
#   ruby session-stats.rb 2debd0eb-a474-4abf-bb63-8575bc52a52a --task bb166270

require 'json'
require 'time'
require 'optparse'

class SessionStats
  CLAUDE_WORK_PATH = File.expand_path('~/.claude-work/projects/-Users-liu-atdd-hub')

  def self.find_latest_session
    # 找到最新修改的 .jsonl 檔案
    jsonl_files = Dir.glob(File.join(CLAUDE_WORK_PATH, '*.jsonl'))
    return nil if jsonl_files.empty?

    latest = jsonl_files.max_by { |f| File.mtime(f) }
    File.basename(latest, '.jsonl')
  end

  def initialize(session_id, options = {})
    @session_id = session_id == 'latest' ? self.class.find_latest_session : session_id
    @since = options[:since] ? Time.parse(options[:since]) : nil
    @task_id = options[:task_id]
    @stats = {
      tools: Hash.new(0),
      tokens: { input: 0, output: 0, cache_read: 0, cache_creation: 0 },
      agents: Hash.new { |h, k| h[k] = { tools: 0, tokens: 0, duration_ms: 0 } },
      total_tools: 0,
      start_time: nil,
      end_time: nil
    }
    # Task tool_use id → subagent_type 的對應表
    @pending_tasks = {}
  end

  def calculate
    jsonl_path = File.join(CLAUDE_WORK_PATH, "#{@session_id}.jsonl")

    unless File.exist?(jsonl_path)
      puts "Error: Session file not found: #{jsonl_path}"
      exit 1
    end

    File.foreach(jsonl_path) do |line|
      next if line.strip.empty?

      begin
        record = JSON.parse(line)
        process_record(record)
      rescue JSON::ParserError
        next
      end
    end

    @stats
  end

  def process_record(record)
    timestamp = record['timestamp'] ? Time.parse(record['timestamp']) : nil

    # 如果有 since 過濾條件
    return if @since && timestamp && timestamp < @since

    # 如果有 task_id 過濾條件，檢查是否在任務開始之後
    if @task_id && !@task_start_found
      if record['type'] == 'user' && record.dig('message', 'content')&.include?(@task_id)
        @task_start_found = true
        @stats[:start_time] = timestamp
      end
      return unless @task_start_found
    end

    @stats[:start_time] ||= timestamp if timestamp
    @stats[:end_time] = timestamp if timestamp

    case record['type']
    when 'assistant'
      process_assistant(record)
    when 'user'
      process_user(record)
    end
  end

  def process_assistant(record)
    message = record['message'] || {}

    # Main agent 的 token 統計
    usage = message['usage'] || {}
    @stats[:tokens][:input] += usage['input_tokens'].to_i
    @stats[:tokens][:output] += usage['output_tokens'].to_i
    @stats[:tokens][:cache_read] += usage['cache_read_input_tokens'].to_i
    @stats[:tokens][:cache_creation] += usage['cache_creation_input_tokens'].to_i

    main_tokens = usage['input_tokens'].to_i + usage['output_tokens'].to_i +
                  usage['cache_read_input_tokens'].to_i + usage['cache_creation_input_tokens'].to_i

    # Tool 使用統計 — assistant record 中的 tool_use 全部屬於 main
    content = message['content'] || []
    content.each do |item|
      next unless item.is_a?(Hash) && item['type'] == 'tool_use'

      tool_name = item['name']
      @stats[:tools][tool_name] += 1
      @stats[:total_tools] += 1
      @stats[:agents]['main'][:tools] += 1

      # 記錄 Task 呼叫，等 tool_result 時配對
      if tool_name == 'Task'
        agent_type = item.dig('input', 'subagent_type')
        @pending_tasks[item['id']] = agent_type if agent_type
      end
    end

    @stats[:agents]['main'][:tokens] += main_tokens
  end

  def process_user(record)
    content = (record.dig('message', 'content') || [])
    return unless content.is_a?(Array)

    content.each do |item|
      next unless item.is_a?(Hash) && item['type'] == 'tool_result'

      tool_use_id = item['tool_use_id']
      agent_type = @pending_tasks.delete(tool_use_id)
      next unless agent_type

      # 從 toolUseResult 讀取 subagent 的精確統計
      tur = record['toolUseResult']
      next unless tur.is_a?(Hash)

      agent = @stats[:agents][agent_type]
      agent[:tools] += tur['totalToolUseCount'].to_i
      agent[:tokens] += tur['totalTokens'].to_i
      agent[:duration_ms] += tur['totalDurationMs'].to_i

      @stats[:total_tools] += tur['totalToolUseCount'].to_i
    end
  end

  def format_tokens(count)
    if count >= 1_000_000
      "#{(count / 1_000_000.0).round(1)}M"
    elsif count >= 1_000
      "#{(count / 1_000.0).round(1)}k"
    else
      count.to_s
    end
  end

  def format_duration
    return 'N/A' unless @stats[:start_time] && @stats[:end_time]

    format_duration_ms((@stats[:end_time] - @stats[:start_time]).to_i * 1000)
  end

  def format_duration_ms(ms)
    seconds = ms / 1000
    if seconds >= 3600
      hours = seconds / 3600
      minutes = (seconds % 3600) / 60
      "#{hours}h #{minutes}m"
    elsif seconds >= 60
      minutes = seconds / 60
      secs = seconds % 60
      "#{minutes}m #{secs}s"
    else
      "#{seconds}s"
    end
  end

  def to_s
    total_input = @stats[:tokens][:input] + @stats[:tokens][:cache_read] + @stats[:tokens][:cache_creation]
    total_output = @stats[:tokens][:output]
    total_tokens = total_input + total_output

    lines = []
    lines << "## Session Statistics"
    lines << ""
    lines << "### Summary"
    lines << "- **Total Tools**: #{@stats[:total_tools]}"
    lines << "- **Total Tokens**: #{format_tokens(total_tokens)} (Input: #{format_tokens(total_input)}, Output: #{format_tokens(total_output)})"
    lines << "- **Duration**: #{format_duration}"
    lines << ""

    if @stats[:agents].any?
      lines << "### By Agent"
      @stats[:agents].each do |agent, data|
        duration_str = data[:duration_ms] > 0 ? " / #{format_duration_ms(data[:duration_ms])}" : ""
        lines << "- **#{agent}**: #{data[:tools]} tools / #{format_tokens(data[:tokens])} tokens#{duration_str}"
      end
      lines << ""
    end

    if @stats[:tools].any?
      lines << "### Top Tools"
      @stats[:tools].sort_by { |_, count| -count }.first(10).each do |tool, count|
        lines << "- #{tool}: #{count}"
      end
    end

    lines.join("\n")
  end

  def to_json
    total_input = @stats[:tokens][:input] + @stats[:tokens][:cache_read] + @stats[:tokens][:cache_creation]
    total_output = @stats[:tokens][:output]

    {
      totalTools: @stats[:total_tools],
      totalTokens: total_input + total_output,
      inputTokens: total_input,
      outputTokens: total_output,
      duration: format_duration,
      agents: @stats[:agents].transform_values do |data|
        h = { tools: data[:tools], tokens: format_tokens(data[:tokens]) }
        h[:duration] = format_duration_ms(data[:duration_ms]) if data[:duration_ms] > 0
        h
      end,
      topTools: @stats[:tools].sort_by { |_, count| -count }.first(10).to_h
    }.to_json
  end

  def to_compact_format
    # 產生精簡格式的 agents 統計
    agent_stats = @stats[:agents].map do |agent, data|
      "#{agent}(#{data[:tools]}/#{format_tokens(data[:tokens])})"
    end.join(', ')

    total_input = @stats[:tokens][:input] + @stats[:tokens][:cache_read] + @stats[:tokens][:cache_creation]
    total_output = @stats[:tokens][:output]
    total_tokens = total_input + total_output

    "**Agents**: #{agent_stats}\n**總計**: #{@stats[:total_tools]} tools / #{format_tokens(total_tokens)} tokens / #{format_duration}"
  end
end

# CLI
if __FILE__ == $0
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: #{$0} <session_id> [options]"

    opts.on('--since TIMESTAMP', 'Filter records since this ISO8601 timestamp') do |ts|
      options[:since] = ts
    end

    opts.on('--task TASK_ID', 'Filter records for this task (partial match)') do |id|
      options[:task_id] = id
    end

    opts.on('--format FORMAT', 'Output format: text, json, compact') do |format|
      options[:format] = format
    end

    opts.on('-h', '--help', 'Show this help') do
      puts opts
      exit
    end
  end.parse!

  session_id = ARGV[0]
  unless session_id
    puts "Error: Session ID required"
    puts "Usage: #{$0} <session_id> [--since <timestamp>] [--task <task_id>] [--format text|json|compact]"
    exit 1
  end

  stats = SessionStats.new(session_id, options)
  stats.calculate

  case options[:format]
  when 'json'
    puts stats.to_json
  when 'compact'
    puts stats.to_compact_format
  else
    puts stats.to_s
  end
end
