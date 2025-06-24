import time
import pandas as pd
import gspread
import pytz
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

# --- Selenium 스크래핑 함수 (제공해주신 코드와 동일) ---
def scrape_with_selenium():
    """Selenium을 사용하여 Google Trends의 실시간 검색어를 스크래핑합니다."""
    url = "https://trends.google.com/trending?geo=KR&hours=4"
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    try:
        print("🔍 Selenium으로 Chrome 브라우저를 실행합니다...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        print("   - JavaScript 데이터 로딩 대기 중 (3초)...")
        time.sleep(3)
        html_source = driver.page_source
        driver.quit()
        print("✅ 페이지 소스 가져오기 성공!")
        soup = BeautifulSoup(html_source, 'lxml')
        table_body = soup.find('tbody', jsname='cC57zf')
        if not table_body:
            print("❌ 검색어 테이블을 찾을 수 없습니다. (tbody 태그 없음)")
            return None
        rows = table_body.find_all('tr')
        if len(rows) == 0:
            print("❌ 검색어 데이터를 찾을 수 없습니다. (tr 태그 없음)")
            return None
        keywords = [row.find('div', class_='mZ3RIc').get_text(strip=True) for row in rows if row.find('div', class_='mZ3RIc')]
        print(f"✅ Selenium 스크래핑 성공! ({len(keywords)}개 키워드 발견)")
        return keywords
    except Exception as e:
        print(f"❌ Selenium 실행 중 오류 발생: {e}")
        if 'driver' in locals() and driver:
            driver.quit()
        return None

# --- 기존 update_google_sheet 함수를 아래 코드로 전체 교체 ---
def update_google_sheet(data_df):
    """스크래핑한 데이터를 기준 시간과 함께 Google Sheet에 업데이트합니다."""
    try:
        print("🔄 Google Sheet에 연결을 시도합니다...")
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)

        sheet = client.open("블로그 실시간 검색어").sheet1
        print(f"   - '{sheet.title}' 시트에 연결 성공!")

        # 시트 내용 전체 삭제
        sheet.clear()

        # --- 시간 정보 추가 로직 ---
        # 1. 한국 시간대 설정
        kst = pytz.timezone('Asia/Seoul')
        # 2. 현재 한국 시간 가져오기
        now_kst = datetime.now(kst)
        # 3. 원하는 형식으로 텍스트 만들기 (예: (06월 24일 14시))
        timestamp_text = now_kst.strftime('(%m월 %d일 %H시)')
        
        # 4. A1 셀에 기준 시간 텍스트 저장
        sheet.update_acell('A1', timestamp_text)
        print(f"✅ 기준 시간 '{timestamp_text}'을(를) A1셀에 저장했습니다.")
        # --- 로직 끝 ---

        # B1 셀부터 키워드 데이터 저장
        if not data_df.empty:
            sheet.update('B1', [data_df.columns.values.tolist()] + data_df.values.tolist())
            print("✅ 키워드 목록을 B1셀부터 저장했습니다.")
        else:
            print("⚠️ 업데이트할 데이터가 없습니다.")

    except FileNotFoundError:
        print("❌ 'credentials.json' 파일을 찾을 수 없습니다.")
    except gspread.exceptions.SpreadsheetNotFound:
        print("❌ '블로그 실시간 검색어' 시트를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ Google Sheet 작업 중 오류 발생: {e}")

# --- 메인 실행 부분 ---
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Google Trends 스크래핑 및 시트 업데이트 시스템 시작")
    print("=" * 50)
    
    # 1. 셀레니움으로 트렌드 키워드 가져오기
    trending_keywords = scrape_with_selenium() 
    
    # 2. 키워드 목록을 구글 시트에 저장하기
    if trending_keywords:
        # 리스트를 Pandas DataFrame으로 변환 (시트에 저장하기 위함)
        trends_df = pd.DataFrame(trending_keywords, columns=['검색어'])
        
        print("\n--- [ 저장할 키워드 목록 ] ---")
        print(trends_df)
        print("-" * 30 + "\n")
        
        # Google Sheet 업데이트 함수 호출
        update_google_sheet(trends_df)
    else:
        print("\n키워드를 가져오지 못해 Google Sheet를 업데이트할 수 없습니다.")
        
    print("\n✅ 모든 작업이 완료되었습니다.")
