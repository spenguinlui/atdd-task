# frozen_string_literal: true

require 'rails_helper'

# CST-170 Regression Tests — 案場頁面版本歷程清單必須完整列出全部版本（含 canceled）
#
# Bug：/admin/project_management/projects/GC040002 只顯示 v1~v3，v4~v7 消失。
#
# Root cause：
#   頁面版本清單來源 = project_entity.version_histories
#                    = Wrapper#find_by 的 old_versions（WHERE created_at <= anchor.created_at）
#   anchor = find_latest_version 取得的「最新非 canceled 版本」
#   當 v4~v7 的 created_at 晚於 anchor.created_at，被上界裁掉而消失。
#
# 修復方向（業主已定案，spec Solution Overview）：
#   version_histories 應載入「該案場全部版本」（無 created_at 上界、無 status 過濾），
#   與 first_approval? 用的 old_versions（created_at <= anchor）資料來源分離。
#
# 本檔在修復前應 RED：
#   S1 / S2 期望 version_histories 列出全部 7 筆，現況只回 3 筆 → 失敗。
#   S3 期望 first_approval? / project_approved 語意不變（CST-145）→ 修復前後皆應綠（regression baseline）。
RSpec.describe 'CST-170 版本歷程清單完整性 (version_histories)', type: :model do
  let(:repo) { ProjectManagement::Project::Repositories::Project.new }

  # 時間 mock 隔離（規則 4）：所有 created_at 都以固定基準計算，避免測試間時間污染。
  let(:base_time) { Time.zone.parse('2026-01-01 10:00:00') }

  # 建立 7 版本 fixture，重現 anchor = v3、v4~v7 created_at 晚於 anchor 的觸發條件。
  #
  # @param serial_number  案場代碼
  # @param v4_to_v7_status v4~v7 的 status（S1 用 canceled 證明 show-all；S2 可換非 canceled）
  def build_seven_versions(serial_number:, v4_to_v7_status: 'canceled')
    pm = ProjectManagement::Project::Models
    project = pm::Project.create!(serial_number: serial_number, name: "案場#{serial_number}", alias: "別名#{serial_number}")

    statuses = {
      '1' => 'approved',
      '2' => 'approved',
      '3' => 'pending_approval', # v3 = 最新非 canceled 版本 = find_latest_version 的 anchor
      '4' => v4_to_v7_status,
      '5' => v4_to_v7_status,
      '6' => v4_to_v7_status,
      '7' => v4_to_v7_status,
    }

    # created_at 嚴格遞增 v1 < v2 < ... < v7，確保 old_versions(created_at <= v3.created_at) 只涵蓋 v1~v3。
    (1..7).each do |i|
      pm::ProjectVersion.create!(
        project_id: project.id,
        version_serial_number: i.to_s,
        status: statuses[i.to_s],
        created_at: base_time + i.hours,
        submitted_at: base_time + i.hours,
      )
    end

    project
  end

  # ----------------------------------------------------------------------
  # S1-happy：完整列出全部 7 個版本（含 canceled）
  # ----------------------------------------------------------------------
  describe 'S1-happy: version_histories 完整列出全部 7 筆（含 canceled）' do
    before { build_seven_versions(serial_number: 'CST170S1', v4_to_v7_status: 'canceled') }

    let(:entity) { repo.find_latest_version(serial_number: 'CST170S1') }
    let(:serials) { entity.version_histories.map(&:version_serial_number) }

    it 'version_histories 筆數為 7（修復前只有 3）' do
      expect(entity.version_histories.size).to eq(7)
    end

    it 'version_serial_number 升冪為 1..7' do
      expect(serials).to eq(%w[1 2 3 4 5 6 7])
    end

    it '修復前缺漏的 v4,v5,v6,v7 四列皆存在' do
      expect(serials).to include('4', '5', '6', '7')
    end

    it 'canceled 版本（v4~v7）仍在版本歷程中（show-all 規則）' do
      canceled_serials = entity.version_histories.select(&:canceled?).map(&:version_serial_number)
      expect(canceled_serials).to eq(%w[4 5 6 7])
    end
  end

  # ----------------------------------------------------------------------
  # S2-edge：anchor 為 v3、v4~v7 created_at 較晚的觸發重現（不依賴 production）
  # ----------------------------------------------------------------------
  describe 'S2-edge: anchor=v3、v4~v7 created_at 晚於 anchor 仍須完整列出' do
    before { build_seven_versions(serial_number: 'CST170S2', v4_to_v7_status: 'canceled') }

    let(:entity) { repo.find_latest_version(serial_number: 'CST170S2') }

    it 'find_latest_version 取得的 anchor 確實為 v3（最新非 canceled）' do
      # 證明 fixture 觸發條件成立：anchor 為 v3，old_versions 上界 = v3.created_at。
      expect(entity.version_serial_number).to eq('3')
    end

    it '即使 anchor=v3，版本歷程清單筆數仍為 7（與 old_versions 上界解耦）' do
      expect(entity.version_histories.size).to eq(7)
    end

    it 'version_serial_number 升冪為 1..7（v4~v7 不被 created_at 上界裁切）' do
      serials = entity.version_histories.map(&:version_serial_number)
      expect(serials).to eq(%w[1 2 3 4 5 6 7])
    end

    context '當 v4~v7 為非 canceled（如 draft）時亦須完整列出' do
      before do
        # 重建為非 canceled 的 v4~v7；此時 find_latest_version 的 anchor 會變成 v7。
        ProjectManagement::Project::Models::Project.where(serial_number: 'CST170S2EDGE').destroy_all
        build_seven_versions(serial_number: 'CST170S2EDGE', v4_to_v7_status: 'draft')
      end

      it '版本歷程清單筆數仍為 7' do
        e = repo.find_latest_version(serial_number: 'CST170S2EDGE')
        expect(e.version_histories.size).to eq(7)
        expect(e.version_histories.map(&:version_serial_number)).to eq(%w[1 2 3 4 5 6 7])
      end
    end
  end

  # ----------------------------------------------------------------------
  # S2-edge 邊界補強：字典序 vs 數值序（AC3）
  # ----------------------------------------------------------------------
  describe 'S2-edge boundary: 版本歷程依數值序排序（非字典序 10 < 2）' do
    it '含 v10 時排序為 1..10 數值升冪，而非字典序' do
      pm = ProjectManagement::Project::Models
      project = pm::Project.create!(serial_number: 'CST170NUM', name: '數值序案場', alias: '別名')
      (1..10).each do |i|
        pm::ProjectVersion.create!(
          project_id: project.id,
          version_serial_number: i.to_s,
          status: i <= 3 ? 'approved' : 'canceled',
          created_at: base_time + i.hours,
          submitted_at: base_time + i.hours,
        )
      end

      entity = repo.find_latest_version(serial_number: 'CST170NUM')
      serials = entity.version_histories.map(&:version_serial_number)

      expect(serials).to eq(%w[1 2 3 4 5 6 7 8 9 10])
    end
  end

  # ----------------------------------------------------------------------
  # S3-regression：first_approval? / project_approved 語意不變（守 CST-145）
  # ----------------------------------------------------------------------
  describe 'S3-regression: first_approval? / project_approved 不因本修復改變' do
    let(:project) { create(:project_management_project) }

    context '案場 A：old_versions 僅含當前 approved 版本、無更早 approved（從未有更早 approved_at）' do
      let!(:v1) do
        create(:project_management_project_version,
               project_id: project.id, version_serial_number: '1',
               status: 'approved', created_at: base_time, submitted_at: base_time)
      end
      let!(:v1_eng) do
        create(:project_management_approval_process,
               project_version_id: v1.id, process: 'engineering',
               approval_type: 'human', approved_at: base_time)
      end
      let!(:v1_fin) do
        create(:project_management_approval_process,
               project_version_id: v1.id, process: 'finance',
               approval_type: 'human', approved_at: base_time)
      end

      it 'first_approval? 為 true、project_approved 為 false' do
        entity = repo.find_by_version_number(serial_number: project.serial_number, version_serial_number: '1')
        expect(entity.first_approval?).to eq(true)
        expect(entity.project_approved).to eq(false)
      end
    end

    context '案場 B：存在 created_at 早於 anchor 的真正 approved 版本（曾有 approved_at）' do
      let!(:v1) do
        create(:project_management_project_version,
               project_id: project.id, version_serial_number: '1',
               status: 'approved', created_at: base_time, submitted_at: base_time)
      end
      let!(:v1_eng) do
        create(:project_management_approval_process,
               project_version_id: v1.id, process: 'engineering',
               approval_type: 'human', approved_at: base_time)
      end
      let!(:v1_fin) do
        create(:project_management_approval_process,
               project_version_id: v1.id, process: 'finance',
               approval_type: 'human', approved_at: base_time)
      end
      let!(:v2) do
        create(:project_management_project_version,
               project_id: project.id, version_serial_number: '2',
               status: 'pending_approval', created_at: base_time + 1.hour, submitted_at: base_time + 1.hour)
      end
      let!(:v2_eng) do
        create(:project_management_approval_process,
               project_version_id: v2.id, process: 'engineering',
               approval_type: 'human', approved_at: nil)
      end

      it 'first_approval? 為 false、project_approved 為 true' do
        entity = repo.find_by_version_number(serial_number: project.serial_number, version_serial_number: '2')
        expect(entity.first_approval?).to eq(false)
        expect(entity.project_approved).to eq(true)
      end
    end
  end
end
