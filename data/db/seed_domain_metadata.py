#!/usr/bin/env python3
"""Seed domain metadata: Chinese names and descriptions.

Derived from domain-map.md files + business knowledge.
Upserts into knowledge_terms (as domain-level UL terms) and
updates domains table description via a new metadata JSONB column
or uses knowledge_entries with file_type='domain-profile'.

Usage:
    python seed_domain_metadata.py --db postgresql://atdd:atdd@localhost:5435/atdd
"""

import argparse
import os
import sys

import psycopg2
import psycopg2.extras

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://atdd:atdd@localhost:5435/atdd"
)
DEFAULT_ORG = "00000000-0000-0000-0000-000000000001"

# ============================================================
# Domain Registry: english_name -> (chinese_name, description_zh, domain_type)
# Compiled from domain-map.md files across all projects
# ============================================================
DOMAIN_REGISTRY = {
    # === core_web (40 domains from codebase /domains/) ===
    "Account": {
        "project": "core_web",
        "chinese_name": "帳戶管理",
        "type": "Supporting",
        "description": "管理用戶帳戶基本資料和帳戶狀態。",
    },
    "Atm": {
        "project": "core_web",
        "chinese_name": "ATM 轉帳",
        "type": "Supporting",
        "description": "處理 ATM 虛擬帳號的產生和轉帳對帳。",
    },
    "Blog": {
        "project": "core_web",
        "chinese_name": "部落格",
        "type": "Generic",
        "description": "官方網站的部落格/文章管理功能。",
    },
    "Cart": {
        "project": "core_web",
        "chinese_name": "購物車",
        "type": "Supporting",
        "description": "投資認購流程中的購物車功能，管理認購項目和結帳流程。",
    },
    "Charity": {
        "project": "core_web",
        "chinese_name": "公益專案",
        "type": "Supporting",
        "description": "管理公益型電廠專案的特殊業務邏輯。",
    },
    "CommunicationModule": {
        "project": "core_web",
        "chinese_name": "通訊模組",
        "type": "Generic",
        "description": "統一的通訊發送模組（Email、SMS、推播等），供各 domain 使用。",
    },
    "Company": {
        "project": "core_web",
        "chinese_name": "公司管理",
        "type": "Supporting",
        "description": "管理法人客戶和公司資料。",
    },
    "Contract": {
        "project": "core_web",
        "chinese_name": "合約管理",
        "type": "Supporting",
        "description": "管理合約類型判斷（代管/租賃）、換約流程和合約範本，影響電費呈現和發票開立。",
    },
    "Crowdfund": {
        "project": "core_web",
        "chinese_name": "群眾募資",
        "type": "Core",
        "description": "管理電廠群眾募資流程，包含募資專案設定、進度追蹤和投資人參與。",
    },
    "Discount": {
        "project": "core_web",
        "chinese_name": "折扣優惠",
        "type": "Supporting",
        "description": "管理各類折扣碼和優惠活動。",
    },
    "DurationProfit": {
        "project": "core_web",
        "chinese_name": "期間收益",
        "type": "Core",
        "description": "計算各期間的投資收益分配。",
    },
    "ElectricityAccounting": {
        "project": "core_web",
        "chinese_name": "電費會計",
        "type": "Core",
        "description": "計算電費收入、支出、稅差調整等會計項目，為 ERP 憑單和款項發放提供帳款來源。",
    },
    "ElectricityAccounting::ChargesCalculation::RuleBasedCharge": {
        "project": "core_web",
        "chinese_name": "電費計費：規則式費用",
        "type": "Core",
        "description": "根據業務規則自動計算電費中的各項費用（如維運費、管理費），適用於非固定金額的動態計算場景。",
    },
    "ElectricityAccounting::ChargesCalculation::FixedCharge": {
        "project": "core_web",
        "chinese_name": "電費計費：固定費用",
        "type": "Core",
        "description": "處理固定金額的電費項目計算，如電錶租費等固定收取的費用。",
    },
    "ElectricityAccounting::FixedCharge": {
        "project": "core_web",
        "chinese_name": "電費固定費用",
        "type": "Core",
        "description": "管理固定收取的電費項目（電錶租費等），與 ChargesCalculation::FixedCharge 協作。",
    },
    "ElectricityAccounting::PeriodicLedger": {
        "project": "core_web",
        "chinese_name": "電費週期帳本",
        "type": "Core",
        "description": "管理每期電費的帳務記錄，追蹤各用戶應收/應付金額，產生 DueDetail 供 ERP 週期使用。",
    },
    "ElectricityAccounting::ProjectEntry": {
        "project": "core_web",
        "chinese_name": "電費專案分錄",
        "type": "Core",
        "description": "處理電費按專案分錄的記帳邏輯，將電費收支對應到各電廠專案。",
    },
    "ElectricityBilling": {
        "project": "core_web",
        "chinese_name": "電費帳單",
        "type": "Core",
        "description": "產生電費帳單（含屋頂租金），作為 ERP 週期和款項發放的 Source 來源之一。",
    },
    "ElectricityBilling::RoofRental": {
        "project": "core_web",
        "chinese_name": "電費帳單：屋頂租金",
        "type": "Core",
        "description": "管理屋頂租金的帳單計算，屋主租金收入的來源，供款項發放流程使用。",
    },
    "Tools::ErpPeriod": {
        "project": "core_web",
        "chinese_name": "ERP 週期管理",
        "type": "Supporting",
        "description": "管理 ERP 憑單的批次生命週期（建立、審核、開票、拋送），編排 Source → Document 轉換流程。系統中任務量最大的 domain。",
    },
    "Tools::ErpPeriod::SourceConversion": {
        "project": "core_web",
        "chinese_name": "ERP 來源轉換",
        "type": "Supporting",
        "description": "負責將各種帳款來源（ElectricBillAccount、RoofRentalAccount、DueDetail）轉換為 ERP Document。",
    },
    "Tools::DigiwinErp": {
        "project": "core_web",
        "chinese_name": "鼎新 ERP 整合",
        "type": "Supporting",
        "description": "管理鼎新 ERP 系統的憑單建立、單別路由（DocumentTypeNo）、專案對照和 API 拋送。",
    },
    "Receipt": {
        "project": "core_web",
        "chinese_name": "電子發票",
        "type": "Supporting",
        "description": "透過綠界 ECPay API 管理電子發票的開立（電費單發票、維運費發票）和折讓。",
    },
    "PaymentTransfer": {
        "project": "core_web",
        "chinese_name": "款項發放",
        "type": "Supporting",
        "description": "管理款項發放全流程：DueRecord 建立、PaymentRound 批次發放、ACH 銀行檔案產生與回應處理。",
    },
    "Revenue": {
        "project": "core_web",
        "chinese_name": "營收管理",
        "type": "Core",
        "description": "管理用戶應收/應發金額（Due），作為 ERP 週期和款項發放的核心來源。",
    },
    "RoofRental": {
        "project": "core_web",
        "chinese_name": "屋頂租賃",
        "type": "Core",
        "description": "管理屋頂租賃合約、租金計算和屋主關係。",
    },
    "RoofDevelopment::SalesManagement": {
        "project": "core_web",
        "chinese_name": "屋頂開發：業務管理",
        "type": "Core",
        "description": "管理電廠屋頂開發的業務流程，包含 CRM 商機追蹤（Opportunity）和業務團隊管理。",
    },
    "Admin": {
        "project": "core_web",
        "chinese_name": "後台管理",
        "type": "Generic",
        "description": "後台管理介面的通用功能，包含頁面佈局、選單和共用元件。",
    },
    "Admin::UI": {
        "project": "core_web",
        "chinese_name": "後台介面元件",
        "type": "Generic",
        "description": "後台管理系統的 UI 元件和前端互動邏輯。",
    },
    "Authentication": {
        "project": "core_web",
        "chinese_name": "身份認證",
        "type": "Supporting",
        "description": "管理使用者登入、Session 管理和身份驗證機制。",
    },
    "Authorization": {
        "project": "core_web",
        "chinese_name": "權限管理",
        "type": "Supporting",
        "description": "角色型存取控制（RBAC），管理使用者角色和功能權限。",
    },
    "Analytics": {
        "project": "core_web",
        "chinese_name": "數據分析",
        "type": "Supporting",
        "description": "提供營運數據統計和報表功能，如發電量分析、收益統計等。",
    },
    "Monitoring": {
        "project": "core_web",
        "chinese_name": "系統監控",
        "type": "Supporting",
        "description": "監控系統運行狀態、排程任務執行狀況和異常告警。",
    },
    "Experimental": {
        "project": "core_web",
        "chinese_name": "實驗性功能",
        "type": "Generic",
        "description": "實驗中的功能模組，尚未正式上線的新功能。",
    },
    "ExternalNotifier": {
        "project": "core_web",
        "chinese_name": "外部通知",
        "type": "Generic",
        "description": "對外部系統發送通知（如 Slack、LINE 等外部服務）。",
    },
    "Frontpage": {
        "project": "core_web",
        "chinese_name": "官方首頁",
        "type": "Generic",
        "description": "官方網站首頁和公開頁面的內容管理。",
    },
    "Frontpage::ContactForm": {
        "project": "core_web",
        "chinese_name": "官網聯絡表單",
        "type": "Generic",
        "description": "官方網站的聯絡我們表單功能。",
    },
    "InternalNotifier": {
        "project": "core_web",
        "chinese_name": "內部通知",
        "type": "Generic",
        "description": "系統內部通知機制（站內信、通知中心）。",
    },
    "Invoice": {
        "project": "core_web",
        "chinese_name": "發票管理",
        "type": "Supporting",
        "description": "管理發票開立的共用邏輯，與 Receipt domain 協作。",
    },
    "Line": {
        "project": "core_web",
        "chinese_name": "LINE 整合",
        "type": "Generic",
        "description": "LINE 官方帳號整合：帳號綁定、訊息推播、Webhook 處理。",
    },
    "MarketingCampaigns": {
        "project": "core_web",
        "chinese_name": "行銷活動",
        "type": "Supporting",
        "description": "管理行銷活動和推廣方案。",
    },
    "MonitoringSources": {
        "project": "core_web",
        "chinese_name": "監控資料來源",
        "type": "Supporting",
        "description": "管理發電監控的資料來源設定和串接。",
    },
    "Order": {
        "project": "core_web",
        "chinese_name": "訂單管理",
        "type": "Core",
        "description": "管理投資認購訂單的建立、付款、退款和狀態變更。",
    },
    "Ownership": {
        "project": "core_web",
        "chinese_name": "產權管理",
        "type": "Core",
        "description": "管理電廠板片的產權歸屬和移轉。",
    },
    "ProgramSale": {
        "project": "core_web",
        "chinese_name": "方案銷售",
        "type": "Core",
        "description": "管理投資方案的銷售設定和庫存。",
    },
    "ProjectDetail": {
        "project": "core_web",
        "chinese_name": "專案詳情",
        "type": "Supporting",
        "description": "電廠專案的詳細資訊展示和內容管理。",
    },
    "ProjectElectricity": {
        "project": "core_web",
        "chinese_name": "專案電力",
        "type": "Core",
        "description": "管理電廠的發電量資料、電力計算和電力相關設定。",
    },
    "ProjectFacade": {
        "project": "core_web",
        "chinese_name": "專案門面",
        "type": "Supporting",
        "description": "電廠專案的統一查詢介面（Facade），整合多個 domain 的專案資訊。",
    },
    "ProjectProfile": {
        "project": "core_web",
        "chinese_name": "專案檔案",
        "type": "Supporting",
        "description": "電廠專案的基本資料和設定管理。",
    },
    "ProjectSale": {
        "project": "core_web",
        "chinese_name": "專案銷售",
        "type": "Core",
        "description": "管理電廠專案的銷售流程和投資人配置。",
    },
    "RenewableEnergy": {
        "project": "core_web",
        "chinese_name": "再生能源",
        "type": "Core",
        "description": "再生能源憑證和綠電相關業務邏輯。",
    },
    "Report": {
        "project": "core_web",
        "chinese_name": "報表",
        "type": "Supporting",
        "description": "各類營運報表的產生和匯出。",
    },
    "RoofOwner": {
        "project": "core_web",
        "chinese_name": "屋主管理",
        "type": "Supporting",
        "description": "管理屋頂出租屋主的資料、合約和聯絡資訊。",
    },
    "SiteManagement": {
        "project": "core_web",
        "chinese_name": "場域管理",
        "type": "Supporting",
        "description": "管理電廠場域（site）的基本資料和設定。",
    },
    "Tools::KgiPaymentReceiver": {
        "project": "core_web",
        "chinese_name": "凱基銀行收款",
        "type": "Supporting",
        "description": "處理凱基銀行的收款通知和對帳。",
    },
    "Tools::RoofOwnerNotify": {
        "project": "core_web",
        "chinese_name": "屋主通知工具",
        "type": "Supporting",
        "description": "屋主相關的批次通知發送工具。",
    },
    "Tools::Site": {
        "project": "core_web",
        "chinese_name": "場域工具",
        "type": "Supporting",
        "description": "場域管理的輔助工具。",
    },
    "Tools::YearsCashFlow": {
        "project": "core_web",
        "chinese_name": "年度現金流工具",
        "type": "Supporting",
        "description": "計算和分析電廠專案的年度現金流。",
    },

    # === core_web_frontend ===
    "InfrastructureAutomation": {
        "project": "core_web_frontend",
        "chinese_name": "基礎設施自動化",
        "type": "Supporting",
        "description": "前端部署自動化和 CI/CD 基礎設施管理。",
    },

    # === aws_infra ===
    # Note: same domain name, different project
    "InfrastructureAutomation__aws_infra": {
        "project": "aws_infra",
        "chinese_name": "AWS 基礎設施自動化",
        "type": "Supporting",
        "description": "AWS EC2 實例管理、部署流程自動化和基礎設施即代碼。",
        "domain_name": "InfrastructureAutomation",
    },

    # === sf_project ===
    "Accounting": {
        "project": "sf_project",
        "chinese_name": "會計總帳",
        "type": "Core",
        "description": "管理專案的整體會計作業，包含應收、應付和發票管理的上層 Bounded Context。",
    },
    "Accounting::AccountsReceivable": {
        "project": "sf_project",
        "chinese_name": "應收帳款",
        "type": "Core",
        "description": "管理專案的應收帳款，依工程進度節點判斷請款條件，與 ERP 結帳單整合。",
    },
    "Accounting::AccountsPayable": {
        "project": "sf_project",
        "chinese_name": "應付帳款",
        "type": "Core",
        "description": "管理專案的應付帳款（含作廢機制），依工程進度節點判斷期程款可請款狀態。",
    },
    "Accounting::Invoice": {
        "project": "sf_project",
        "chinese_name": "發票管理",
        "type": "Core",
        "description": "管理專案相關的發票開立、折讓和發票追蹤。",
    },
    "Project::Management": {
        "project": "sf_project",
        "chinese_name": "專案管理",
        "type": "Core",
        "description": "管理電廠建置專案的生命週期，包含專案基本資料、版本控制和狀態追蹤。",
    },
    "ProjectFund": {
        "project": "sf_project",
        "chinese_name": "專案資金",
        "type": "Core",
        "description": "管理專案資金的申請、多級審核流程和 ERP 撥款。",
    },
    "Receipt__sf": {
        "project": "sf_project",
        "chinese_name": "收據管理",
        "type": "Supporting",
        "description": "管理專案相關的收據開立、列印和狀態追蹤。",
        "domain_name": "Receipt",
    },
    "ShippingOrderManagement": {
        "project": "sf_project",
        "chinese_name": "出貨單管理",
        "type": "Supporting",
        "description": "管理設備出貨單的建立、追蹤和簽收流程。",
    },
    "PurchaseReceiptManagement": {
        "project": "sf_project",
        "chinese_name": "進貨單管理",
        "type": "Supporting",
        "description": "管理設備進貨單的建立、驗收和入庫流程。",
    },
    "Tools::DigiwinErp__sf": {
        "project": "sf_project",
        "chinese_name": "鼎新 ERP 整合",
        "type": "Generic",
        "description": "sf_project 與鼎新 ERP 系統的結帳單同步和資料整合。",
        "domain_name": "Tools::DigiwinErp",
    },

    "ContractManagement": {
        "project": "sf_project",
        "chinese_name": "合約管理",
        "type": "Supporting",
        "description": "管理工程合約的建立、變更和追蹤。",
    },
    "FileManagement": {
        "project": "sf_project",
        "chinese_name": "檔案管理",
        "type": "Generic",
        "description": "管理專案相關文件的上傳、分類和存取。",
    },
    "MasterData": {
        "project": "sf_project",
        "chinese_name": "主檔管理",
        "type": "Generic",
        "description": "管理系統共用的基礎資料（廠商、材料、規格等主檔）。",
    },
    "ProjectManagement": {
        "project": "sf_project",
        "chinese_name": "專案工程管理",
        "type": "Core",
        "description": "管理工程專案的進度、工程節點和期程款映射。",
    },
    "Reporting": {
        "project": "sf_project",
        "chinese_name": "報表",
        "type": "Supporting",
        "description": "專案相關的營運報表和統計分析。",
    },
    "Admin__sf": {
        "project": "sf_project",
        "chinese_name": "後台管理",
        "type": "Generic",
        "description": "sf_project 專案管理系統的後台管理介面。",
        "domain_name": "Admin",
    },
    "Tool::BatchUpload": {
        "project": "sf_project",
        "chinese_name": "批次上傳工具",
        "type": "Generic",
        "description": "批次匯入資料的通用上傳工具。",
    },
    "Tool::Notifier": {
        "project": "sf_project",
        "chinese_name": "通知工具",
        "type": "Generic",
        "description": "系統通知發送工具。",
    },
    "Tool::Postmark": {
        "project": "sf_project",
        "chinese_name": "Postmark 郵件",
        "type": "Generic",
        "description": "透過 Postmark 服務發送交易型電子郵件。",
    },
    "Tool::Functions": {
        "project": "sf_project",
        "chinese_name": "通用函式庫",
        "type": "Generic",
        "description": "專案共用的工具函式。",
    },

    # === e_trading (7 top-level + 14 PowerWheeling sub-domains) ===
    "Admin__et": {
        "project": "e_trading",
        "chinese_name": "後台管理",
        "type": "Generic",
        "description": "e_trading 綠電交易平台的後台管理介面。",
        "domain_name": "Admin",
    },
    "CustomerManagement": {
        "project": "e_trading",
        "chinese_name": "客戶管理",
        "type": "Supporting",
        "description": "管理綠電交易客戶（用電戶）的基本資料和合約關係。",
    },
    "DispatchManagement": {
        "project": "e_trading",
        "chinese_name": "調度管理",
        "type": "Core",
        "description": "管理綠電調度排程和電力分配。",
    },
    "Erp__et": {
        "project": "e_trading",
        "chinese_name": "ERP 整合",
        "type": "Generic",
        "description": "e_trading 與鼎新 ERP 系統的資料整合。",
        "domain_name": "Erp",
    },
    "ProjectTransfer": {
        "project": "e_trading",
        "chinese_name": "專案移轉",
        "type": "Supporting",
        "description": "管理綠電專案的移轉和交接流程。",
    },
    "PowerWheeling": {
        "project": "e_trading",
        "chinese_name": "轉供電力",
        "type": "Core",
        "description": "綠電轉供交易的核心 Bounded Context，包含合約、結算、帳務、調度等子域。",
    },
    "PowerWheeling::AccountingResult": {
        "project": "e_trading",
        "chinese_name": "轉供電力結算",
        "type": "Core",
        "description": "管理綠電轉供交易的電力結算結果，包含服務費設定和稅差調整。",
    },
    "PowerWheeling::Account": {
        "project": "e_trading",
        "chinese_name": "轉供帳戶",
        "type": "Core",
        "description": "管理轉供交易的帳戶資料和餘額。",
    },
    "PowerWheeling::ActorsManagement": {
        "project": "e_trading",
        "chinese_name": "轉供參與者管理",
        "type": "Core",
        "description": "管理轉供交易的各參與方（發電業者、售電業者、用電戶）。",
    },
    "PowerWheeling::BillingResult": {
        "project": "e_trading",
        "chinese_name": "轉供帳單結果",
        "type": "Core",
        "description": "產生轉供交易的帳單計算結果。",
    },
    "PowerWheeling::CompositionManagement": {
        "project": "e_trading",
        "chinese_name": "轉供組成管理",
        "type": "Core",
        "description": "管理轉供電力的組成結構（電源組合）。",
    },
    "PowerWheeling::CppaContract": {
        "project": "e_trading",
        "chinese_name": "CPPA 合約",
        "type": "Core",
        "description": "管理企業購電合約（Corporate PPA）的建立和生命週期。",
    },
    "PowerWheeling::CppaContractSource": {
        "project": "e_trading",
        "chinese_name": "CPPA 合約來源",
        "type": "Core",
        "description": "管理 CPPA 合約的電源來源設定。",
    },
    "PowerWheeling::ExternalCommunication": {
        "project": "e_trading",
        "chinese_name": "轉供外部通訊",
        "type": "Supporting",
        "description": "管理與台電、能源局等外部單位的資料交換。",
    },
    "PowerWheeling::ProgressManagement": {
        "project": "e_trading",
        "chinese_name": "轉供進度管理",
        "type": "Supporting",
        "description": "追蹤轉供案件的申請進度和狀態。",
    },
    "PowerWheeling::RawResult": {
        "project": "e_trading",
        "chinese_name": "轉供原始結果",
        "type": "Core",
        "description": "儲存從台電取得的原始轉供電力數據。",
    },
    "PowerWheeling::ResultApplication": {
        "project": "e_trading",
        "chinese_name": "轉供結果應用",
        "type": "Core",
        "description": "將原始轉供結果轉化為可用的帳務和帳單資料。",
    },
    "PowerWheeling::RetailerSettings": {
        "project": "e_trading",
        "chinese_name": "售電業者設定",
        "type": "Supporting",
        "description": "管理售電業者的費率、條件和合約設定。",
    },
    "PowerWheeling::Settlement": {
        "project": "e_trading",
        "chinese_name": "轉供結算",
        "type": "Core",
        "description": "執行轉供交易的結算流程，計算各方應收應付。",
    },
    "PowerWheeling::WheelingResult": {
        "project": "e_trading",
        "chinese_name": "轉供結果",
        "type": "Core",
        "description": "最終的轉供電力計算結果，作為帳單和結算的依據。",
    },
    "Tool__et_notifier": {
        "project": "e_trading",
        "chinese_name": "通知工具",
        "type": "Generic",
        "description": "e_trading 的系統通知工具。",
        "domain_name": "Tool::Notifier",
    },
    "Tool__et_receipt": {
        "project": "e_trading",
        "chinese_name": "收據工具",
        "type": "Supporting",
        "description": "e_trading 的收據開立工具。",
        "domain_name": "Tool::Receipt",
    },
    "Tool__et_site": {
        "project": "e_trading",
        "chinese_name": "場域工具",
        "type": "Generic",
        "description": "e_trading 場域管理的輔助工具。",
        "domain_name": "Tool::Site",
    },
    "Tool__et_tags": {
        "project": "e_trading",
        "chinese_name": "標籤工具",
        "type": "Generic",
        "description": "資料標籤管理工具。",
        "domain_name": "Tool::Tags",
    },

    # === jv_project ===
    "Admin__jv": {
        "project": "jv_project",
        "chinese_name": "後台管理",
        "type": "Generic",
        "description": "jv_project 合資專案管理系統的後台管理介面。",
        "domain_name": "Admin",
    },

    # === stock_commentary ===
    "StockData::DataGovernance": {
        "project": "stock_commentary",
        "chinese_name": "股票資料治理",
        "type": "Core",
        "description": "管理股票資料的品質控管、資料源驗證和資料一致性檢查。",
    },
    "DataBackfill": {
        "project": "stock_commentary",
        "chinese_name": "歷史資料回補",
        "type": "Supporting",
        "description": "批次回補歷史股票資料，處理資料缺漏和補正。",
    },
}


def seed(db_url: str, org_id: str, dry_run: bool = False):
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # First, ensure domains table has a metadata column
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'domains' AND column_name = 'metadata'
    """)
    if not cur.fetchone():
        if dry_run:
            print("[DRY-RUN] Would add metadata JSONB column to domains table")
        else:
            cur.execute("ALTER TABLE domains ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'")
            print("Added metadata column to domains table")

    created = 0
    updated = 0

    for key, info in DOMAIN_REGISTRY.items():
        domain_name = info.get("domain_name", key)
        project = info["project"]
        chinese = info["chinese_name"]
        desc = info["description"]
        dtype = info["type"]

        metadata = {
            "chinese_name": chinese,
            "description": desc,
            "domain_type": dtype,
        }

        if dry_run:
            print(f"  [{project}] {domain_name} → {chinese} ({dtype})")
            continue

        # Update domains table metadata
        cur.execute("""
            UPDATE domains SET metadata = metadata || %s::jsonb
            WHERE org_id = %s AND project = %s AND name = %s
        """, (psycopg2.extras.Json(metadata), org_id, project, domain_name))

        if cur.rowcount == 0:
            # Domain doesn't exist yet in domains table, insert it
            cur.execute("""
                INSERT INTO domains (org_id, project, name, metadata, calculated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (org_id, project, name) DO UPDATE SET
                    metadata = domains.metadata || EXCLUDED.metadata
            """, (org_id, project, domain_name, psycopg2.extras.Json(metadata)))
            created += 1
        else:
            updated += 1

        # Also upsert as UL term for domain name
        cur.execute("""
            INSERT INTO knowledge_terms (org_id, project, domain, english_term, chinese_term, context, source)
            VALUES (%s, %s, %s, %s, %s, %s, 'domain-registry')
            ON CONFLICT (org_id, project, english_term) DO UPDATE SET
                chinese_term = EXCLUDED.chinese_term,
                context = EXCLUDED.context,
                source = EXCLUDED.source
        """, (org_id, project, domain_name, domain_name, chinese, desc))

    conn.close()

    if dry_run:
        print(f"\n[DRY-RUN] Would process {len(DOMAIN_REGISTRY)} domains")
    else:
        print(f"\nDone. Updated: {updated}, Created: {created}, Total: {len(DOMAIN_REGISTRY)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed domain metadata")
    parser.add_argument("--db", default=DEFAULT_DB_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seed(args.db, DEFAULT_ORG, dry_run=args.dry_run)
