import time
import pandas as pd
import gspread
import pytz
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait # 🔴 지능적인 대기를 위해 추가
from selenium.webdriver.support import expected_conditions as EC # 🔴 지능적인 대기를 위해 추가
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import json
import sys

# --- 1. Google Trends 스크래핑 함수 (변경 없음) ---
def scrape_google_trends():
    """Selenium을 사용하여 Google Trends의 실시간 검색어를 스크래핑합니다."""
    # ... (이전과 동일, 변경 없음)
    url = "https://trends.google.com/trending?geo=KR&hours=4"
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = None
    try:
        print("🔍 [Google] Selenium으로 Chrome 브라우저를 실행합니다...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        print("   - JavaScript 데이터 로딩 대기 중 (3초)...")
        time.sleep(3)
        html_source = driver.page_source
        print("✅ [Google] 페이지 소스 가져오기 성공!")
        
        soup = BeautifulSoup(html_source, 'lxml')
        table_body = soup.find('tbody', jsname='cC57zf')
        if not table_body:
            print("❌ [Google] 검색어 테이블을 찾을 수 없습니다.")
            return None
        
        rows = table_body.find_all('tr')
        if not rows:
            print("❌ [Google] 검색어 데이터를 찾을 수 없습니다.")
            return None
            
        keywords = [row.find('div', class_='mZ3RIc').get_text(strip=True) for row in rows if row.find('div', class_='mZ3RIc')]
        print(f"✅ [Google] 스크래핑 성공! ({len(keywords)}개 키워드 발견)")
        return keywords

    except Exception as e:
        print(f"❌ [Google] Selenium 실행 중 오류 발생: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# --- 2. ZUM 트렌드 스크래핑 함수 (2페이지 수집 기능 최종 수정) ---
def scrape_zum_trends():
    """[최종 수정] Selenium으로 '더보기'를 클릭하고 1, 2페이지 키워드를 모두 스크래핑합니다."""
    url = "https://m.zum.com"
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = None
    try:
        print("🔍 [ZUM] 'AI 이슈 트렌드' 스크래핑을 시작합니다...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        # 초기 로딩이 충분히 되도록 명시적으로 기다립니다.
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ai-issue-trend"))
        )
        print("   - 페이지 초기 로딩 완료.")
        
        # --- 1페이지 스크래핑 ---
        html_source_p1 = driver.page_source
        soup_p1 = BeautifulSoup(html_source_p1, 'lxml')
        container_p1 = soup_p1.select_one('div.ai-issue-trend')
        if not container_p1:
            print("❌ [ZUM] 'AI 이슈 트렌드' 컨테이너를 찾을 수 없습니다.")
            return None
        
        keyword_tags_p1 = container_p1.select('.title-box p.title span')
        keywords_p1 = [tag.get_text(strip=True) for tag in keyword_tags_p1]
        print(f"✅ [ZUM] 1페이지 스크래핑 성공! ({len(keywords_p1)}개)")

        all_keywords = list(keywords_p1)

        # --- 2페이지 스크래핑 로직 ---
        try:
            print("   - '더보기' 버튼 클릭 시도...")
            # 1. '더보기' 버튼을 찾아서 클릭합니다.
            more_button = driver.find_element(By.CSS_SELECTOR, 'button.btn-issue-more')
            driver.execute_script("arguments[0].click();", more_button) # JS 클릭으로 더 확실하게
            
            # 2. 페이지 번호가 '2'로 바뀔 때까지 최대 5초간 기다립니다.
            WebDriverWait(driver, 5).until(
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, 'span.current-page'), '2')
            )
            print("   - 2페이지 로딩 완료.")
            
            # 3. 2페이지 내용 스크래핑
            html_source_p2 = driver.page_source
            soup_p2 = BeautifulSoup(html_source_p2, 'lxml')
            container_p2 = soup_p2.select_one('div.ai-issue-trend')
            if container_p2:
                keyword_tags_p2 = container_p2.select('.title-box p.title span')
                keywords_p2 = [tag.get_text(strip=True) for tag in keyword_tags_p2]
                all_keywords.extend(keywords_p2)
                print(f"✅ [ZUM] 2페이지 스크래핑 성공! ({len(keywords_p2)}개)")

        except Exception:
            print("   - 2페이지를 가져오지 못했습니다. 1페이지 결과만 사용합니다.")

        # 중복 제거 후 최종 리스트 반환
        final_keywords = list(dict.fromkeys(all_keywords))
        
        if not final_keywords:
            print("❌ [ZUM] 최종 키워드를 추출하지 못했습니다.")
            return None
        
        print(f"✅ [ZUM] 최종 스크래핑 성공! (총 {len(final_keywords)}개 키워드 발견)")
        return final_keywords

    except Exception as e:
        print(f"❌ [ZUM] Selenium 실행 중 오류 발생: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# --- 3. NATE 트렌드 크롤러 함수 (변경 없음) ---
def scrape_nate_trends():
    """NATE의 실시간 이슈 키워드 JSON 데이터를 직접 가져옵니다."""
    try:
        print("🔍 [NATE] 실시간 이슈 키워드 API 요청을 시작합니다...")
        now = datetime.now().strftime('%Y%m%d%H%M')
        url = f'https://www.nate.com/js/data/jsonLiveKeywordDataV1.js?v={now}'
        response = requests.get(url)
        response.raise_for_status()
        data = response.content.decode('euc-kr')
        keyword_list = json.loads(data)
        keywords = [item[1] for item in keyword_list]
        print(f"✅ [NATE] 데이터 수신 성공! ({len(keywords)}개 키워드 발견)")
        return keywords
    except Exception as e:
        print(f"❌ [NATE] 알 수 없는 오류 발생: {e}")
        return None

# --- 4. Google Sheet 업데이트 함수 (변경 없음) ---
def update_google_sheet(google_data, zum_data, nate_data):
    """3개의 트렌드 데이터를 취합하여 Google Sheet에 업데이트합니다."""
    try:
        print("\n🔄 Google Sheet에 연결을 시도합니다...")
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open("블로그 실시간 검색어").sheet1
        print(f"   - '{sheet.title}' 시트에 연결 성공!")

        sheet.clear()

        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        timestamp_text = now_kst.strftime('(%m월 %d일 %H시 업데이트)')
        sheet.update_acell('A1', timestamp_text)
        print(f"✅ 기준 시간 '{timestamp_text}'을(를) A1셀에 저장했습니다.")

        google_series = pd.Series(google_data, name='Google 트렌드')
        zum_series = pd.Series(zum_data, name='ZUM 트렌드')
        nate_series = pd.Series(nate_data, name='NATE 트렌드')
        
        combined_df = pd.concat([google_series, zum_series, nate_series], axis=1)

        if not combined_df.empty:
            combined_df.fillna('', inplace=True)
            data_to_update = [combined_df.columns.values.tolist()] + combined_df.values.tolist()
            sheet.update(range_name='A2', values=data_to_update, value_input_option='USER_ENTERED')
            print("✅ Google, ZUM, NATE 키워드 목록을 A2셀부터 저장했습니다.")
        else:
            print("⚠️ 업데이트할 데이터가 없습니다.")

    except FileNotFoundError:
        print("❌ 'credentials.json' 파일을 찾을 수 없습니다. Google Cloud Console에서 생성 후, 코드와 같은 폴더에 저장해주세요.")
    except gspread.exceptions.SpreadsheetNotFound:
        print("❌ Google Sheet에서 '블로그 실시간 검색어' 스프레드시트를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ Google Sheet 작업 중 오류 발생: {e}")
        # GitHub Actions에 실패 상태(Exit Code 1)를 명시적으로 전달
        sys.exit(1)

# --- 메인 실행 부분 (변경 없음) ---
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Google, ZUM, NATE 트렌드 스크래핑 및 시트 업데이트 시스템 시작")
    print("=" * 50)
    
    google_keywords = scrape_google_trends()
    print("-" * 50)
    zum_keywords = scrape_zum_trends()
    print("-" * 50)
    nate_keywords = scrape_nate_trends()
    
    if google_keywords or zum_keywords or nate_keywords:
        update_google_sheet(google_keywords, zum_keywords, nate_keywords)
    else:
        print("\n모든 소스에서 키워드를 가져오지 못해 Google Sheet를 업데이트할 수 없습니다.")
        
    print("\n✅ 모든 작업이 완료되었습니다.")
