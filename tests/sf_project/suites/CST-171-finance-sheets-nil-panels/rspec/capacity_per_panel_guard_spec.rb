# frozen_string_literal: true

require 'rails_helper'

# CST-171 — finance_sheets 缺模組片數開啟即 500 修正
# Task: 649bc99a-17b5-47f6-bb5c-eee5972eeb2e
#
# 驗收根因：retrieve_finance_sheets_dto.rb:57 capacity_per_panel
#   (entity.detail.total_capacity * 1000 / entity.detail.number_of_panels).to_i
#   number_of_panels=nil → TypeError: nil can't be coerced into BigDecimal
#   number_of_panels=0   → ZeroDivisionError / FloatDomainError
#
# 此檔為 unit 層回歸測試（DB stub）。E2E（真瀏覽器頁面提示文字）見 suite scenarios。
RSpec.describe ProjectManagement::ProjectDocument::UseCases::RetrieveFinanceSheetsDto do
  let(:serial_number) { 'RT020056' }
  let(:version_serial_number) { '1' }

  let(:incoming_contract) do
    ProjectManagement::Project::Entities::Project::IncomingContract.new(
      total_income_without_tax: total_income_without_tax,
      client: build(:client_entity),
    )
  end

  let(:detail) do
    ProjectManagement::Project::Entities::Project::ProjectDetail.new(
      total_capacity: total_capacity,
      number_of_panels: number_of_panels,
      estimated_daily_generation: BigDecimal('3.7'),
      taipower_rate: BigDecimal('6.0537'),
    )
  end

  let(:financial_plan) do
    ProjectManagement::Project::Entities::Project::FinancialPlan.new(
      sale_price_per_kw: 50_000,
      roof_rental_ratio: BigDecimal('0.08'),
      equipment_insurance_ratio: BigDecimal('0.0035'),
      maintenance_fee_ratio: BigDecimal('0.012'),
      inverter_installment_ratio: BigDecimal('0.005'),
      degradation_ratio: BigDecimal('0.007'),
      roof_rental_fixed_amount: 0,
    )
  end

  let(:entity) do
    build(:project_entity, :approved).tap do |e|
      allow(e).to receive(:incoming_contract).and_return(incoming_contract)
      allow(e).to receive(:detail).and_return(detail)
      allow(e).to receive(:financial_plan).and_return(financial_plan)
      allow(e).to receive(:cost_elements).and_return([])
    end
  end

  let(:use_case) do
    described_class.new(
      serial_number: serial_number,
      version_serial_number: version_serial_number,
    )
  end

  before do
    allow(ProjectManagement::Project::Client).to receive(:new).and_return(
      double('ProjectClient', retrieve_project: entity),
    )
    allow(ProjectManagement::ProjectDocument::UseCases::RetrieveFinanceSheetsDto::EstimateFormula)
      .to receive(:new).and_return(
        double('EstimateFormula', profit: 1_000_000, irr: 850, cash_table: []),
      )
  end

  # ==========================================================
  # S1-error: number_of_panels = nil（RT020056 v1 真實根因）
  # ==========================================================
  describe 'S1-error: number_of_panels is nil' do
    let(:number_of_panels) { nil }
    let(:total_capacity) { BigDecimal('13.0') }
    let(:total_income_without_tax) { 5_500_000 }

    it 'does NOT raise TypeError (nil coerced into BigDecimal) in capacity_per_panel' do
      expect { use_case.capacity_per_panel }.not_to raise_error
    end

    it 'does NOT raise any error in build_dto (whole page would 500 otherwise)' do
      expect { use_case.build_dto }.not_to raise_error
    end

    it 'capacity_per_panel returns a missing-data sentinel, not a fabricated number' do
      # 缺模組片數無法算單片容量 → 不得回傳有限整數除法值。
      # 預期回傳 nil（讓 view 判定缺資料）。
      expect(use_case.capacity_per_panel).to be_nil
    end
  end

  # ==========================================================
  # S2-edge: number_of_panels = 0
  # ==========================================================
  describe 'S2-edge: number_of_panels is 0' do
    let(:number_of_panels) { 0 }
    let(:total_capacity) { BigDecimal('13.0') }
    let(:total_income_without_tax) { 5_500_000 }

    it 'does NOT raise ZeroDivisionError / FloatDomainError in capacity_per_panel' do
      expect { use_case.capacity_per_panel }.not_to raise_error
    end

    it 'does NOT raise any error in build_dto' do
      expect { use_case.build_dto }.not_to raise_error
    end

    it 'capacity_per_panel returns missing-data sentinel (nil), not a fabricated number' do
      expect(use_case.capacity_per_panel).to be_nil
    end
  end

  # ==========================================================
  # S4-regression: 正常案場 RT130033 v1 數值不變
  #   number_of_panels=22, total_capacity=9.79
  #   capacity_per_panel = (9.79 * 1000 / 22).to_i = 445
  # ==========================================================
  describe 'S4-regression: normal project (RT130033 v1 baseline)' do
    let(:number_of_panels) { 22 }
    let(:total_capacity) { BigDecimal('9.79') }
    let(:total_income_without_tax) { 708_796 }

    it 'capacity_per_panel returns the exact pre-fix integer 445' do
      expect(use_case.capacity_per_panel).to eq(445)
    end

    it 'sale_price_per_kw is unchanged (zero-diff)' do
      # 708,796 / 9.79 = 72,400.0... -> present_number -> "72,400"
      expect(use_case.sale_price_per_kw).to eq('72,400')
    end

    it 'total_cost is unchanged (zero-diff, document_cost=0)' do
      # 708,796 + 0 = 708,796 -> "708,796"
      expect(use_case.total_cost).to eq('708,796')
    end

    it 'build_dto does not raise for a complete project' do
      expect { use_case.build_dto }.not_to raise_error
    end

    it 'build_dto exposes capacity 445 and quantity 22 in parameters' do
      dto = use_case.build_dto
      expect(dto[:parameters][:capacity]).to eq(445)
      expect(dto[:parameters][:quantity]).to eq(22)
    end
  end
end
