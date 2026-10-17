"""Optional OFFLINE browser/HTTP QA; requires preinstalled Playwright/Chromium.

All model/detector responses come from the explicitly labeled fixture process.
This script never downloads a browser or bypasses navigation restrictions.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    output = ROOT / 'reports/browser-local'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='clearwrite-browser-') as folder:
        metadata = Path(folder) / 'server.json'
        process = subprocess.Popen([sys.executable, str(ROOT / 'tests/fixtures/serve_ui_fixture.py'),
                                    '--metadata', str(metadata)],
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 10
            while not metadata.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Offline fixture failed to start')
                time.sleep(.05)
            url = json.loads(metadata.read_text())['url']
            checks = []
            with sync_playwright() as playwright:
                executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
                options = {'executable_path': executable} if executable else {}
                browser = playwright.chromium.launch(headless=True, **options)
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url)
                page.get_by_role('button', name='예시 체험', exact=True).click()
                page.locator('#changes .change-item').nth(1).wait_for()
                page.locator('#result [data-change="2"]').press('Enter')
                assert page.locator('#changes .active').get_attribute('data-change') == '2'
                checks.append('linked_highlights_and_keyboard')
                with page.expect_download() as download:
                    page.locator('#save-report').click()
                download.value.save_as(str(output / 'offline-report.json'))
                report = json.loads((output / 'offline-report.json').read_text(encoding='utf-8'))
                assert report['demonstration'] and report['model_requests'] == 0
                checks.append('download_matches_demo')
                page.locator('#model-consent').check()
                page.locator('#style-analyze').click()
                page.get_by_text('AI 문체 분석을 마쳤습니다.', exact=False).wait_for()
                assert page.locator('#ai-before').inner_text() == '21'
                assert page.locator('#style-before-reasons blockquote').count() > 0
                assert page.locator('#change-rate').inner_text().endswith('%')
                checks.append('offline_model_style_scores_reasons_and_actual_change_rate')
                page.get_by_text('모델 지정', exact=True).click()
                page.locator('#model').fill('fixture-failure')
                previous_output = page.locator('#result').inner_text()
                page.locator('#model-consent').check()
                page.locator('#style-analyze').click()
                page.get_by_text('분석을 완료하지 못했습니다.', exact=False).wait_for()
                assert page.locator('#ai-before').inner_text() == '미분석'
                assert page.locator('#result').inner_text() == previous_output
                checks.append('failed_style_assessment_preserves_edits_without_fake_zero')
                page.screenshot(path=str(output / 'desktop-offline.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(output / 'mobile-offline.png'), full_page=True)
                checks.append('mobile_no_horizontal_overflow')
                assert not errors, errors
                browser.close()
                (output / 'validation.json').write_text(json.dumps({
                    'checks': checks, 'javascript_errors': errors, 'model_requests': 0,
                    'paid_model_calls': 0, 'scope': 'real HTTP browser with explicit offline fixtures'
                }, indent=2), encoding='utf-8')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()