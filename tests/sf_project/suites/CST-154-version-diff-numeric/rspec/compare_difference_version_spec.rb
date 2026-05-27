# frozen_string_literal: true
#
# CST-154 CompareDifferenceVersion use case acceptance tests
#
# Place into the sf_project repo at:
#   spec/domains/project_management/project/use_cases/compare_difference_version_cst154_spec.rb
#
# Coverage:
#   S1-happy   : current=10, previous=9
#   S6-error   : URL version_serial_number 不存在 -> 不可 fallback 到 draft
#   S7-regression: 無 version_serial_number -> 走既有 confirmed-pending 比對流（保留 fallback）

require 'rails_helper'

RSpec.describe ProjectManagement::Project::UseCases::CompareDifferenceVersion, '(CST-154)' do
  let(:use_case) { described_class.new }
  let!(:project) { create(:project_management_project, serial_number: 'RT020040') }
  let!(:business_partner) { create(:business_partner_record, identity: '82860463') }

  def make_version(serial:, status:, submitted_at: nil)
    create(
      :project_management_project_version,
      project_id: project.id,
      version_serial_number: serial,
      status: status,
      submitted_at: submitted_at,
    )
  end

  describe 'S1-happy: 點擊版本 10 應顯示 current=10, previous=9' do
    before do
      (8..10).each { |n| make_version(serial: n.to_s, status: 'approved') }
      make_version(serial: '11', status: 'draft')
    end

    it 'comparison_info.current_version == "10" and previous_version == "9"' do
      result = use_case.call(serial_number: 'RT020040', version_serial_number: '10')
      expect(result).to be_success
      _diffs, info = result.value!
      expect(info[:current_version]).to eq('10')
      expect(info[:previous_version]).to eq('9')
    end

    it 'current_version_id corresponds to ProjectVersion id of version 10' do
      v10 = ProjectManagement::Project::Models::ProjectVersion
            .where(project_id: project.id, version_serial_number: '10').first
      result = use_case.call(serial_number: 'RT020040', version_serial_number: '10')
      _diffs, info = result.value!
      expect(info[:current_version_id]).to eq(v10.id)
    end
  end

  describe 'S6-error: URL 指定的版本不存在時不可 fallback 到 draft' do
    before do
      # Real approved versions exist
      make_version(serial: '1', status: 'approved')
      # And there is also a draft (last_updated source)
      make_version(serial: '2', status: 'draft')
    end

    it 'returns Failure (or non-draft error) and does not show draft as current' do
      result = use_case.call(serial_number: 'RT020040', version_serial_number: '99')

      # Strict assertion: when URL version_serial_number is given but not found,
      # the use case must NOT silently substitute the draft.
      if result.success?
        _diffs, info = result.value!
        # Even if the implementation chooses to return Success with empty current,
        # current_version must NOT equal '2' (the draft).
        expect(info[:current_version]).not_to eq('2')
      else
        expect(result).to be_failure
      end
    end
  end

  describe 'S7-regression: 無 version_serial_number 保留 confirmed-pending 流程' do
    before do
      make_version(serial: '5', status: 'approved')
      make_version(serial: '6', status: 'pending_approval')
    end

    it 'previous_version is newest approved (5); does not raise even without URL param' do
      expect {
        @result = use_case.call(serial_number: 'RT020040')
      }.not_to raise_error

      # Use case is allowed to Success or Failure depending on draft availability,
      # but if Success, previous_version must be the newest approved (5),
      # NOT bypassed by the new fallback guard.
      if @result.success?
        _diffs, info = @result.value!
        expect(info[:previous_version]).to eq('5')
      end
    end
  end

  describe 'S9-safety: URL 參數命名相容性' do
    before { make_version(serial: '1', status: 'approved') }

    it 'accepts kwarg :version_serial_number (no rename)' do
      expect {
        use_case.call(serial_number: 'RT020040', version_serial_number: '1')
      }.not_to raise_error
    end
  end
end
