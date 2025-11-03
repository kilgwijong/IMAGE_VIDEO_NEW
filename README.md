# 💻 AI 이미지 & 비디오 생성 프로젝트

이 프로젝트는 Python Django 프레임워크를 기반으로, Google의 최신 생성형 AI 모델을 활용하여 텍스트 프롬프트로부터 이미지와 비디오를 생성하는 웹 애플리케이션입니다.

---

## ✨ 주요 기능 요약

### 👤 사용자 기능 (User Dashboard)
| 기능 | 설명 |
|------|------|
| 이미지 생성 | 텍스트 프롬프트로 AI 이미지 생성 (Google Imagen) |
| 비디오 생성 | 텍스트 프롬프트로 AI 비디오 생성 (Replicate API) |
| 이번달 사용량 조회 | 월별 API 호출 수 / 토큰 사용량 / 예상 비용 제공 |
| 일자별 사용량 그래프 | API 호출량을 날짜 기준 시각화하여 제공 |
| 최근 생성 기록 | 사용자가 생성한 이미지 / 영상 기록 조회 가능 |
| 파일 다운로드 | 생성된 이미지 / 영상 다운로드 가능 |

### 🛠️ 관리자 기능 (Admin Panel)
| 기능 | 설명 |
|------|------|
| 관리자 대시보드 | 신규 가입자 수, 전체 사용자 수, 금일 API 호출 수, 금월 예상 비용 확인 |
| 회원 관리 | 사용자 정보 조회 / 생성 / 수정 / 삭제 가능 |
| 결제 내역 관리 | 사용자 결제 기록 확인 및 영수증 다운로드 가능 |
| API 사용량 관리 | 이번달 API 호출 수, 토큰 사용량, 비용 확인 |
| CSV Export | API 사용량, 비용 등의 데이터 CSV 파일로 내보내기 가능 |

### 📊 데이터 / 분석 / 다운로드 기능
| 항목 | 지원 여부 |
|-------|----------|
| 월별 API 호출 수 집계 | ✅ |
| 토큰 / 비용 자동 계산 | ✅ |
| 일별 사용량 그래프 | ✅ |
| 결제 영수증 다운로드 | ✅ |
| API 사용량 CSV 저장 | ✅ |
| 관리자/사용자 통계 분리 | ✅ |

---

## 🔧 기술 스택

* **백엔드**
  * <img src="https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white">
  * <img src="https://img.shields.io/badge/django-092E20?style=for-the-badge&logo=django&logoColor=white">
* **AI (Google Cloud & Replicate)**
  * Vertex AI SDK (Gemini / Imagen)
  * Gemini API (프롬프트 처리 및 문장 생성)
  * Imagen (이미지 생성 모델)
  * Replicate (비디오 생성 모델)
* **데이터베이스**
  * SQLite3 (기본 설정)

---

## 🧭 기능 흐름도 (Service Flow)

```mermaid
flowchart TD
    A[사용자(User)] -->|회원가입/로그인| B[메인 페이지]
    B --> C[이미지 생성]
    B --> D[비디오 생성]
    B --> E[사용량 대시보드]
    E --> E1[이번달 호출 수]
    E --> E2[토큰/비용]
    E --> E3[일별 그래프]
    E --> E4[최근 생성 기록]

    A2[관리자(Admin)] --> F[관리자 대시보드]
    F --> F1[신규 가입자 수]
    F --> F2[전체 사용자 수]
    F --> F3[금일 API 호출]
    F --> F4[금월 예상 비용]

    F --> G[회원 관리]
    G --> G1[회원정보 조회]
    G --> G2[회원 생성]
    G --> G3[회원 수정]
    G --> G4[회원 삭제]

    F --> H[결제 관리]
    H --> H1[결제 내역 확인]
    H --> H2[영수증 다운로드]

    F --> I[API 사용량 / 비용 관리]
    I --> I1[월별 호출 수]
    I --> I2[토큰 사용량]
    I --> I3[비용 계산]
    I --> I4[CSV Export]
