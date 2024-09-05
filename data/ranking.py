import requests
from bs4 import BeautifulSoup
import cx_Oracle
from datetime import datetime

# 데이터베이스 연결 함수
def get_oracle_connection():
    dsn_tns = cx_Oracle.makedsn('localhost', '1521', sid='xe')
    connection = cx_Oracle.connect(user='base_man', password='1111', dsn=dsn_tns)
    return connection

# 웹 페이지 요청
url = 'https://sports.news.naver.com/kbaseball/index'
response = requests.get(url)

# BeautifulSoup을 사용하여 HTML 파싱
soup = BeautifulSoup(response.content, 'html.parser')

# 팀 순위 데이터 추출
table = soup.find('table', class_='kbo')
rows = table.find_all('tr')[1:]  # 첫 번째 행은 헤더이므로 제외

# 현재 날짜를 가져옴
rank_date = datetime.now().date()

# 데이터베이스 연결
connection = get_oracle_connection()
cursor = connection.cursor()

for row in rows:
    cells = row.find_all('td')
    rank = int(row.find('th').get_text(strip=True).replace('위', ''))
    team_name = cells[0].find('span', class_='name').get_text(strip=True)
    games = int(cells[1].get_text(strip=True))
    wins = int(cells[2].get_text(strip=True))
    draws = int(cells[3].get_text(strip=True))
    losses = int(cells[4].get_text(strip=True))
    win_rate = cells[5].get_text(strip=True)
    game_diff = cells[6].get_text(strip=True)

    # 중복 검사 및 업데이트 논리 추가
    cursor.execute("""
        SELECT COUNT(*) FROM team_rankings WHERE rank = :1 AND rank_date = :2
    """, (rank, rank_date))
    result = cursor.fetchone()

    if result[0] == 0:
        # 데이터베이스에 삽입 (중복이 없을 때만)
        cursor.execute("""
            INSERT INTO team_rankings (rank, team_name, games, wins, draws, losses, win_rate, game_diff, rank_date)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)
        """, (rank, team_name, games, wins, draws, losses, win_rate, game_diff, rank_date))
    else:
        print(f"Duplicate entry found for rank {rank} on date {rank_date}, skipping insertion.")

# 커밋하여 데이터베이스에 변경 사항 저장
connection.commit()

# 연결 종료
cursor.close()
connection.close()

print("데이터 삽입 완료")
