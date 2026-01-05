name: Katabump Auto Renew

on:
  schedule:
    # 每 3 天运行一次
    - cron: '0 0 */3 * *'
  workflow_dispatch:

jobs:
  renew_job:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: Install System Dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y google-chrome-stable xvfb

      - name: Install Python Libs
        run: pip install DrissionPage requests

      - name: Run Renew Script
        env:
          KB_USER: ${{ secrets.KB_USER }}
          KB_PASS: ${{ secrets.KB_PASS }}
          TG_BOT_TOKEN: ${{ secrets.TG_BOT_TOKEN }}
          TG_CHAT_ID: ${{ secrets.TG_CHAT_ID }}
        run: |
          # 模拟 1920x1080 屏幕
          xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python main.py

      - name: Upload Screenshots
        if: always()
        # [关键修复] 必须使用 v4 版本
        uses: actions/upload-artifact@v4
        with:
          name: debug-screenshots
          path: "*.jpg"
