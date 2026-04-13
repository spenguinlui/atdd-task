# Capybara E2E 測試環境指南

> 此文件供 tester（執行 Capybara 測試）和 coder（撰寫 feature spec）共同參考。
> 當 `projects.yml` 有 `capybara` 設定，或 suite.yml 的 executor 含 `capybara` 時，請讀取此文件。

## 環境前置條件

### Chromedriver

`webdrivers` gem（<= 5.3.1）已 deprecated，無法自動下載 Chrome 115+ 的 driver。

本機需手動安裝：
```bash
brew install chromedriver
```

若 macOS Gatekeeper 擋住 binary（symlink broken），從 Chrome for Testing 手動下載：
```bash
# 查看 Chrome 版本
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version

# 下載對應版本（替換版本號）
curl -sL "https://storage.googleapis.com/chrome-for-testing-public/{VERSION}/mac-arm64/chromedriver-mac-arm64.zip" -o /tmp/chromedriver.zip
unzip -o /tmp/chromedriver.zip -d /tmp/
cp /tmp/chromedriver-mac-arm64/chromedriver /opt/homebrew/Caskroom/chromedriver/*/chromedriver-mac-arm64/
xattr -d com.apple.quarantine /opt/homebrew/bin/chromedriver
```

### selenium-webdriver 版本限制

- `selenium-webdriver` 4.x 需要 Ruby >= 3.0
- Ruby 2.6 專案（core_web, e_trading）無法升級，保留 3.8.0 + 手動 chromedriver
- CI 環境可繼續用 Firefox + webdrivers（CI 的 Chrome 版本受控）

### Ruby 版本

各專案用 RVM 管理，執行前切換：
```bash
source "$HOME/.rvm/scripts/rvm" && rvm use $(cat {project_path}/.ruby-version)
```

## Capybara 設定（spec/support/capybara.rb）

### 必要設定

1. **Chrome driver 註冊**（`:chrome_headless`）
2. **PATH 包含 `/opt/homebrew/bin`**（chromedriver 位置）
3. **下載目錄**（`DOWNLOAD_DIR = Rails.root.join('tmp/downloads').to_s`）
4. **預設 driver**：本機 `chrome_headless`，CI 用 `CAPYBARA_DRIVER=firefox_headless` 覆蓋

### Driver 選擇

```ruby
CAPYBARA_DRIVER = (ENV['CAPYBARA_DRIVER'] || 'chrome_headless').to_sym
```

## 撰寫 Feature Spec

### 檔案位置

```
spec/features/admin/{domain}/{feature}_spec.rb
```

### 常見問題

#### Pundit 權限

Admin 後台用 Pundit 授權。`Fixtures::Admin.run` 建立的帳號有 `administrator` role，但特定頁面可能需要額外 policy 設定。

**症狀**：登入成功但頁面回 404（`render_404`），頁面內容是首頁選單。

**解法**：檢查目標 controller 的 `authorized?` 方法和對應的 Pundit policy，在 fixture 中補上必要的 role/permission。

#### Label 與 Input 關聯

自訂 ViewObject 渲染的表單，`<label>` 和 `<input>` 可能沒有標準的 `for` attribute 關聯。

**症狀**：`fill_in '欄位名稱'` 找不到 field。

**解法**：改用 Ransack field name：`fill_in 'q[field_name_cont]', with: value`

#### Feature Test 被全域排除

RSpec 設定可能全域排除 `type: "feature"`。

**解法**：執行時加 `--tag type:feature`：
```bash
bundle exec rspec spec/features/xxx_spec.rb --tag type:feature
```

## 執行方式

```bash
# 單一 spec
bundle exec rspec spec/features/admin/xxx_spec.rb --tag type:feature --format documentation

# 帶 JSON 輸出（供 test-run 解析）
bundle exec rspec spec/features/admin/xxx_spec.rb --tag type:feature --format documentation --format json --out tmp/capybara_results.json

# Headless 模式（不開瀏覽器視窗）
HEADLESS=1 bundle exec rspec spec/features/admin/xxx_spec.rb --tag type:feature
```
