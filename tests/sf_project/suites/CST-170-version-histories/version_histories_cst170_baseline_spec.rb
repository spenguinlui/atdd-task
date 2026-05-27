# frozen_string_literal: true

require 'rails_helper'

# CST-170 Regression Baselines — S4（單版本明細 zero-diff）與 S5（diff baseline 不被污染）
#
# 這兩個場景是「限縮 blast radius」的防守城牆：
#   S4：版本歷程清單 show-all 修復後，單一版本明細（detail/incoming_contract/cost/sale）取數不得改變。
#   S5：版本歷程 show-all 不得污染版本差異比對基準（CR-008，approved-only 數值序），canceled 不得被選為 baseline。
#
# 修復前後皆應綠（regression baseline）。若修復誤動到 detail取數 或 diff baseline 篩選，這裡會紅。
RSpec.describe 'CST-170 Regression Baselines (S4/S5)', type: :model do
  let(:repo) { ProjectManagement::Project::Repositories::Project.new }
  let(:base_time) { Time.zone.parse('2026-01-01 10:00:00') }

  # ----------------------------------------------------------------------
  # S4-regression：單一版本明細頁 zero-diff
  # ----------------------------------------------------------------------
  describe 'S4-regression: 單一版本明細取數固定（detail / incoming_contract zero-diff）' do
    let!(:project) { ProjectManagement::Project::Models::Project.create!(serial_number: 'CST170S4', name: 'S4 案場', alias: 'S4 別名') }

    # 建立 7 版本（重現 show-all 觸發條件），並對 v3 掛上明確的 detail 與 incoming_contract。
    before do
      pm = ProjectManagement::Project::Models
      statuses = { '1' => 'approved', '2' => 'approved', '3' => 'pending_approval',
                   '4' => 'canceled', '5' => 'canceled', '6' => 'canceled', '7' => 'canceled' }
      @versions = {}
      (1..7).each do |i|
        @versions[i.to_s] = pm::ProjectVersion.create!(
          project_id: project.id, version_serial_number: i.to_s, status: statuses[i.to_s],
          created_at: base_time + i.hours, submitted_at: base_time + i.hours,
        )
      end
      v3 = @versions['3']
      pm::ProjectDetail.create!(
        project_version_id: v3.id, total_capacity: BigDecimal('250.5'),
        taipower_rate: BigDecimal('0.18'), taipower_rate_period: '2024',
        case_type: 'roof', source: 'platform',
        estimated_daily_generation: BigDecimal('1000.0'),
      )
      pm::IncomingContract.create!(
        project_version_id: v3.id, contract_number: 'IN-S4-001',
        note: 'S4 baseline note', maintenance_contract_period: 5,
      )
    end

    let(:entity) { repo.find_by_version_number(serial_number: 'CST170S4', version_serial_number: '3') }

    it 'detail.total_capacity 取數固定為 250.5' do
      expect(entity.detail.total_capacity).to eq(BigDecimal('250.5'))
    end

    it 'detail.taipower_rate 取數固定為 0.18' do
      expect(entity.detail.taipower_rate).to eq(BigDecimal('0.18'))
    end

    it 'detail.case_type 取數固定為 roof' do
      expect(entity.detail.case_type).to eq('roof')
    end

    it 'incoming_contract.contract_number 取數固定為 IN-S4-001' do
      expect(entity.incoming_contract.contract_number).to eq('IN-S4-001')
    end

    it 'incoming_contract.note 取數固定為 S4 baseline note' do
      expect(entity.incoming_contract.note).to eq('S4 baseline note')
    end

    it 'cost_elements 為空（fixture 未掛要素，取數結果為空陣列）' do
      expect(entity.cost_elements).to eq([])
    end

    it 'sale_elements 為空（fixture 未掛要素，取數結果為空陣列）' do
      expect(entity.sale_elements).to eq([])
    end
  end

  # ----------------------------------------------------------------------
  # S5-regression：版本差異比對基準不受影響（守 CR-008）
  # ----------------------------------------------------------------------
  describe 'S5-regression: find_previous_approved_version 仍為 approved-only 數值序最大者' do
    let!(:project) { ProjectManagement::Project::Models::Project.create!(serial_number: 'CST170S5', name: 'S5 案場', alias: 'S5 別名') }

    # approved v1, approved v2, canceled v3（created_at 遞增）。
    before do
      pm = ProjectManagement::Project::Models
      pm::ProjectVersion.create!(project_id: project.id, version_serial_number: '1', status: 'approved',
                                 created_at: base_time + 1.hour, submitted_at: base_time + 1.hour)
      pm::ProjectVersion.create!(project_id: project.id, version_serial_number: '2', status: 'approved',
                                 created_at: base_time + 2.hours, submitted_at: base_time + 2.hours)
      pm::ProjectVersion.create!(project_id: project.id, version_serial_number: '3', status: 'canceled',
                                 created_at: base_time + 3.hours, submitted_at: base_time + 3.hours)
    end

    it '當前版本 v3（canceled）的 diff baseline 為 v2（approved 數值序最大且 < 3）' do
      prev = repo.find_previous_approved_version(serial_number: 'CST170S5', version_serial_number: '3')
      expect(prev).to be_present
      expect(prev.version_serial_number).to eq('2')
    end

    it '當前版本 v2 的 diff baseline 為 v1' do
      prev = repo.find_previous_approved_version(serial_number: 'CST170S5', version_serial_number: '2')
      expect(prev).to be_present
      expect(prev.version_serial_number).to eq('1')
    end

    it 'canceled 版本（v3）不會被選為 diff baseline' do
      # 即使存在序號更大的 canceled v3，查 v2 的前一版仍為 v1（approved-only）。
      prev = repo.find_previous_approved_version(serial_number: 'CST170S5', version_serial_number: '4')
      expect(prev.version_serial_number).to eq('2') # v3 canceled 落選，取 approved 數值序最大的 v2
    end

    it 'v1（首個 approved）無更早 approved 版本時 baseline 為 nil' do
      prev = repo.find_previous_approved_version(serial_number: 'CST170S5', version_serial_number: '1')
      expect(prev).to be_nil
    end
  end
end
