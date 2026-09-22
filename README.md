# 2gether

# DB 스키마 설계 문서

## 개요

Snip(단축 URL 및 클릭 분석 서비스)의 데이터베이스 구조를 정의한다.

- **DBMS**: PostgreSQL
- **ORM**: SQLAlchemy
- **정의 위치**: `app/models.py`

## 설계 원칙

1. **최소 구조 유지** — 교과목 목적이 DevOps 파이프라인 구축이므로, 테이블 수를 2개로 제한하고 기능 확장보다 안정적인 데이터 흐름 확보를 우선한다.
2. **인증 제외** — 회원 가입 및 로그인 기능을 개발 범위에서 제외했으므로 사용자 테이블을 두지 않는다. 통계 접근 제어는 추측 불가능한 관리 코드 방식으로 대체한다.
3. **원시 데이터 보존** — 클릭 이벤트를 집계된 숫자가 아닌 개별 레코드로 저장한다. 이후 시간대별·기기별 등 다양한 기준의 통계 산출이 가능하며, 부하 테스트 및 모니터링 시 관측 대상 데이터를 확보할 수 있다.

## 테이블 구조

### urls — 단축 링크 정보

생성된 단축 링크 1건당 1행이 저장된다.

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | SERIAL | PRIMARY KEY | 내부 식별자 (자동 증가) |
| code | VARCHAR(10) | UNIQUE, NOT NULL | 단축 코드. URL 경로에 사용됨 |
| original_url | TEXT | NOT NULL | 원본 URL |
| created_at | TIMESTAMP | DEFAULT NOW() | 생성 시각 |

**설계 근거**

- `code`에 UNIQUE 제약을 부여하여 동일한 단축 코드가 두 번 발급되는 것을 DB 레벨에서 차단한다. 애플리케이션의 중복 검사 로직이 실패하더라도 데이터 정합성이 보장된다.
- `original_url`은 VARCHAR가 아닌 TEXT를 사용한다. URL은 쿼리 파라미터를 포함할 경우 수천 자에 달할 수 있어 길이 제한을 두지 않는다.
- `code` 길이를 10자로 제한한 것은, 62진수(영문 대소문자 + 숫자) 기준 6자리만으로도 약 568억 개의 조합이 가능하여 본 프로젝트 규모에서 충분하기 때문이다.

### clicks — 클릭 이벤트 기록

단축 링크에 접속이 발생할 때마다 1행이 추가된다.

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| id | SERIAL | PRIMARY KEY | 내부 식별자 (자동 증가) |
| url_id | INTEGER | FOREIGN KEY → urls.id, NOT NULL | 대상 링크 |
| clicked_at | TIMESTAMP | DEFAULT NOW() | 클릭 발생 시각 |
| referrer | TEXT | NULL 허용 | 유입 경로 (HTTP Referer 헤더) |
| device | VARCHAR(20) | NULL 허용 | 기기 종류 (User-Agent 기반 판별) |

**설계 근거**

- `referrer`와 `device`는 NULL을 허용한다. 주소창에 직접 입력한 접속은 Referer 헤더가 없고, User-Agent 파싱에 실패하는 경우도 존재하므로 이를 정상 상황으로 처리한다.
- `device`는 `mobile`, `desktop`, `tablet`, `other` 등 제한된 값만 저장하므로 VARCHAR(20)으로 충분하다.
- 집계 결과를 별도 컬럼에 캐싱하지 않는다. 통계는 조회 시점에 SQL 집계 함수로 산출한다.

## 테이블 관계

```
urls (1) ──────< (N) clicks
  id                 url_id
```

하나의 링크에 다수의 클릭 기록이 종속되는 1:N 관계이며, `clicks.url_id`가 `urls.id`를 참조하는 외래키로 연결된다.

**삭제 정책**: 링크 삭제 시 클릭 기록의 처리 방식(CASCADE 삭제 vs 보존)은 팀 협의 후 확정한다. 통계 데이터 보존을 위해 소프트 삭제(삭제 플래그 컬럼 추가) 방식을 권장한다.

## 구현 코드

```python
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Url(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Click(Base):
    __tablename__ = "clicks"
    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=False)
    clicked_at = Column(TIMESTAMP, default=datetime.utcnow)
    referrer = Column(Text, nullable=True)
    device = Column(String(20), nullable=True)
```

## 기능별 데이터 흐름

| 기능 | 동작 |
|---|---|
| F-01 URL 단축 | 단축 코드 생성 후 `urls`에 1행 INSERT |
| F-02 리다이렉트 | `urls`에서 `code`로 조회 → `original_url` 반환 |
| F-03 클릭 수집 | 리다이렉트 시 `clicks`에 1행 INSERT |
| F-04 통계 조회 | `clicks`를 `url_id` 기준으로 집계 (COUNT, GROUP BY) |

