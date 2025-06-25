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
import requests
import json

# --- 1. Google Trends 스크래핑 함수 ---
def scrape_google_trends():
    """Selenium을 사용하여 Google Trends의 실시간 검색어를 스크래핑합니다."""
    # (이전 코드와 동일, 변경 없음)
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

# --- 2. ZUM 트렌드 스크래핑 함수 ---
def scrape_zum_trends():
    """requests와 BeautifulSoup을 사용하여 ZUM의 실시간 검색어를 스크래핑합니다."""
    # (이전 코드와 동일, 변경 없음)
    try:
        print("🔍 [ZUM] 실시간 검색어 스크래핑을 시작합니다...")
        url = 'https://m.search.zum.com/search.zum?method=uni&option=accu&qm=f_typing.top&query='
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html5lib')
        list_wrap = soup.find('div', {'class' : 'list_wrap animate'})
        if not list_wrap: return None

        keyword_tags = list_wrap.find_all('span', {'class' : 'keyword'})
        if not keyword_tags: return None
        
        keywords = [k.text.strip() for k in keyword_tags]
        print(f"✅ [ZUM] 스크래핑 성공! ({len(keywords)}개 키워드 발견)")
        return keywords
    except Exception as e:
        print(f"❌ [ZUM] 스크래핑 중 오류 발생: {e}")
        return None

# --- 3. [신규] NATE 트렌드 크롤러 함수 ---
def scrape_nate_trends():
    """NATE의 실시간 이슈 키워드 JSON 데이터를 직접 가져옵니다."""
    try:
        print("🔍 [NATE] 실시간 이슈 키워드 API 요청을 시작합니다...")
        # 캐시 방지를 위해 현재 시간으로 파라미터 생성
        now = datetime.now().strftime('%Y%m%d%H%M')
        url = f'https://www.nate.com/js/data/jsonLiveKeywordDataV1.js?v={now}'
        
        response = requests.get(url)
        response.raise_for_status()

        # NATE는 euc-kr 인코딩을 사용하므로, 해당 방식으로 디코딩
        data = response.content.decode('euc-kr')
        
        # JSON 형식으로 파싱
        keyword_list = json.loads(data)
        
        # 데이터 구조: ['순위', '키워드', '변동'] -> 여기서 '키워드'만 추출
        keywords = [item[1] for item in keyword_list]
        
        print(f"✅ [NATE] 데이터 수신 성공! ({len(keywords)}개 키워드 발견)")
        return keywords
        
    except requests.exceptions.RequestException as e:
        print(f"❌ [NATE] 요청 중 오류 발생: {e}")
        return None
    except json.JSONDecodeError:
        print("❌ [NATE] JSON 파싱 중 오류가 발생했습니다. 응답 형식이 변경되었을 수 있습니다.")
        return None
    except Exception as e:
        print(f"❌ [NATE] 알 수 없는 오류 발생: {e}")
        return None

# --- 4. [확장] Google Sheet 업데이트 함수 ---
def update_google_sheet(google_data, zum_data, nate_data):
    """3개의 트렌드 데이터를 취합하여 Google Sheet에 업데이트합니다."""
    try:
        print("\n🔄 Google Sheet에 연결을 시도합니다...")
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
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

        # 3개의 데이터 리스트를 Pandas Series로 변환
        google_series = pd.Series(google_data, name='Google 트렌드')
        zum_series = pd.Series(zum_data, name='ZUM 트렌드')
        nate_series = pd.Series(nate_data, name='NATE 트렌드')
        
        # 3개의 Series를 옆으로 이어붙여 하나의 DataFrame 생성
        combined_df = pd.concat([google_series, zum_series, nate_series], axis=1)

        # A2 셀부터 헤더와 데이터 저장
        if not combined_df.empty:
            combined_df.fillna('', inplace=True)
            sheet.update('A2', [combined_df.columns.values.tolist()] + combined_df.values.tolist(), value_input_option='USER_ENTERED')
            print("✅ Google, ZUM, NATE 키워드 목록을 A2셀부터 저장했습니다.")
        else:
            print("⚠️ 업데이트할 데이터가 없습니다.")

    except FileNotFoundError:
        print("❌ 'credentials.json' 파일을 찾을 수 없습니다. Google Cloud Console에서 생성 후, 코드와 같은 폴더에 저장해주세요.")
    except gspread.exceptions.SpreadsheetNotFound:
        print("❌ Google Sheet에서 '블로그 실시간 검색어' 스프레드시트를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ Google Sheet 작업 중 오류 발생: {e}")

# --- 메인 실행 부분 ---
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Google, ZUM, NATE 트렌드 스크래핑 및 시트 업데이트 시스템 시작")
    print("=" * 50)
    
    # 1. 각 포털의 트렌드 키워드 가져오기
    google_keywords = scrape_google_trends()
    print("-" * 50)
    zum_keywords = scrape_zum_trends()
    print("-" * 50)
    nate_keywords = scrape_nate_trends()
    
    # 2. 모든 키워드 목록을 구글 시트에 저장하기
    if google_keywords or zum_keywords or nate_keywords:
        update_google_sheet(google_keywords, zum_keywords, nate_keywords)
    else:
        print("\n모든 소스에서 키워드를 가져오지 못해 Google Sheet를 업데이트할 수 없습니다.")
        
    print("\n✅ 모든 작업이 완료되었습니다.")
