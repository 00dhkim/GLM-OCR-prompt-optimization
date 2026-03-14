# 한국어 OCR 평가용 데이터셋 조사

작성일: 2026-03-14

목적: 한국어 OCR 모델 평가에 쓸 수 있는 데이터셋을 영수증에 한정하지 않고 폭넓게 수집한다. 우선순위는 `평가 적합성`, `라벨 품질`, `접근 가능성`, `도메인 다양성` 기준으로 잡았다.

## 바로 추천하는 조합

실제로 빠르게 평가 세트를 꾸리려면 아래 조합이 가장 현실적이다.

1. `KORIE`
   - 한국어 영수증 OCR 난이도 평가용
   - 실제 열감지 영수증 노이즈가 강해서 모델 차이가 잘 드러남
2. `AI Hub - 다양한 형태의 한글 문자 OCR`
   - 대규모 한글 인쇄체/손글씨 문자·단어 인식 평가용
   - 순수 텍스트 인식 성능을 보기 좋음
3. `AI Hub - 공공행정문서 OCR`
   - 문서형 OCR 평가용
   - 수기/타자체/인쇄체 혼합 문서 검증에 적합
4. `AI Hub - 다중언어 OCR`
   - 한글+영문 혼합 장면문자/표지판 평가용
   - 실제 서비스 환경에 가까운 혼합 스크립트 검증 가능
5. `Hugging Face 소규모 공개셋`
   - 빠른 smoke test 용도
   - 접근은 쉽지만 규모가 작아서 본 평가셋으로는 부족함

## 데이터셋 목록

### 1. KORIE

- 도메인: 한국 소매 영수증
- 성격: 학술 벤치마크
- 규모:
  - MDPI 논문 기준 748장 영수증, 17,587개 OCR crop, 2,886개 IE annotation
  - GitHub 저장소 README 기준 초기 공개본은 774장 영수증으로 표기
- 라벨:
  - 바운딩 박스
  - OCR 전사
  - 항목/금액 등 구조화 정보
- 장점:
  - 한국어 영수증에 특화
  - OCR crop이 따로 있어 recognition-only 평가가 편함
  - split과 평가 코드가 같이 공개됨
- 주의:
  - 논문 수치와 GitHub README 수치가 다르므로 실제 다운로드 시 버전 확인 필요
- 링크:
  - 논문: https://www.mdpi.com/2227-7390/14/1/187
  - 저장소: https://github.com/MahmoudSalah/KORIE

### 2. AI Hub - 다양한 형태의 한글 문자 OCR

- 도메인: 한글 문자 이미지, 인쇄체 + 손글씨
- 성격: 대규모 범용 한글 OCR 학습/평가셋
- 규모:
  - 총 1,176,225건
  - 인쇄체 75,000
  - 필기체 글자 344,412
  - 필기체 단어 756,813
- 라벨:
  - 문자/단어 단위 전사
  - 인쇄체/필기체 구분
- 장점:
  - 한국어 문자 인식 자체를 평가하기 좋음
  - 손글씨와 인쇄체를 같이 커버
  - 문자 수준 에러 분석에 유리
- 주의:
  - 문서 전체 OCR보다는 문자/단어 recognition 평가 쪽에 더 적합
- 링크:
  - https://aihub.or.kr/aidata/33987

### 3. AI Hub - 공공행정문서 OCR

- 도메인: 공공 행정문서
- 성격: 문서형 OCR
- 규모:
  - 이미지 900,000장
- 라벨/특징:
  - 수기, 타자체, 인쇄체 혼합
  - 오래된 문서 스캔/촬영 화질 저하 상황 반영
- 장점:
  - 문서 OCR 실서비스 검증에 적합
  - 한글, 영어, 숫자 혼합 문서 평가 가능
  - 저화질 문서 복원 없이 OCR만 돌렸을 때 약점이 잘 드러남
- 주의:
  - 페이지 OCR과 필드 OCR을 나눠서 평가 계획을 잡는 편이 좋음
  - 페이지 전체 문서라면 현 프로젝트 manifest 형식으로 crop 또는 page text 기준을 먼저 정해야 함
- 링크:
  - https://aihub.or.kr/aidata/30724

### 4. AI Hub - 다중언어 OCR

- 도메인: 한국어-외국어 병기 이미지
- 성격: 장면문자/혼합언어 OCR
- 규모:
  - 400,864건
- 라벨:
  - polygon annotation
  - text language
  - text transcription
- 장점:
  - 한글+영문 혼합 환경에서 OCR 안정성을 보기 좋음
  - 간판, 표지, 실물 환경 텍스트에 가까운 평가가 가능
- 주의:
  - pure Korean OCR보다는 mixed-script robustness 평가에 더 적합
- 링크:
  - https://www.aihub.or.kr/aihubdata/data/view.do?aihubDataSe=data&currMenu=115&dataSetSn=71730&pageIndex=7&srchDetailCnd=DETAILCND001&srchOptnCnd=OPTNCND001&srchOrder=ORDER001&srchPagePer=20&topMenu=100

### 5. AI Hub - OCR 데이터(교육)

- 도메인: 교육 문서
- 성격: 도메인 특화 문서 OCR
- 공개 확인 내용:
  - AI Hub 메인 목록에서 교육 분야 OCR 데이터로 노출
  - 태그에 `공공`, `인쇄체`, `타자체`, `수기`, `행정`, `외교`, `문화`, `과학기술`, `문자인식`, `OCR`가 포함됨
- 장점:
  - 일반 문서가 아니라 교육 관련 포맷을 평가할 때 후보가 됨
  - 수기/인쇄체 혼합 가능성이 높아 범용성 검증에 도움
- 주의:
  - 검색 결과에서 상세 페이지 ID를 바로 확인하지 못했다. 실제 사용 전 AI Hub 내 상세 페이지에서 포맷과 라벨 구조를 재확인해야 한다.
- 링크:
  - https://aihub.or.kr/

### 6. AI Hub - OCR 데이터(금융 및 물류)

- 도메인: 금융/물류 문서
- 성격: 도메인 특화 서식 OCR
- 공개 확인 내용:
  - AI Hub 메인 목록에서 금융 분야 OCR 데이터로 노출
  - 태그에 `선하증권`, `포장명세서`, `상업송장`, `원산지증명서`, `은행`, `증권`, `보험`이 포함됨
- 장점:
  - 영수증 외 상업 문서 OCR 평가에 적합
  - 숫자, 영문, 표 구조가 많은 문서에서 강한 테스트셋이 될 가능성이 큼
- 주의:
  - 상세 페이지 ID를 이번 조사에서는 직접 확인하지 못했다. 도입 전에 샘플과 라벨 포맷 확인 필요
- 링크:
  - https://aihub.or.kr/

### 7. Hugging Face - Korean Handwritten Notes Dataset

- 도메인: 한국어 손글씨 메모
- 성격: 소규모 공개셋
- 규모:
  - 9 rows
  - 약 9.31 MB
- 장점:
  - 접근이 매우 쉬움
  - 필기 OCR smoke test에 유용
- 한계:
  - 너무 작아서 벤치마크 용도로는 부족
- 링크:
  - https://huggingface.co/datasets/HumynLabs/Korean_Handwritten_Notes_Dataset

### 8. Hugging Face - Korean Receipts Dataset

- 도메인: 한국어 영수증
- 성격: 소규모 공개셋
- 규모:
  - 20 rows
  - 약 24 MB
- 장점:
  - 즉시 접근 가능
  - KORIE를 쓰기 전에 파이프라인 smoke test에 적합
- 한계:
  - 규모가 작고 벤치마크 신뢰도가 낮음
- 링크:
  - https://huggingface.co/datasets/HumynLabs/Korean_Receipts_Dataset

### 9. Hugging Face - Korean Price Tags Image Dataset

- 도메인: 가격표/매장 태그
- 성격: 소규모 공개셋
- 규모:
  - 20 rows
- 장점:
  - 숫자+한글 인식 성능을 빠르게 볼 수 있음
  - 리테일 OCR의 보조 검증셋으로 괜찮음
- 한계:
  - 페이지 OCR보다는 짧은 텍스트 인식용
- 링크:
  - https://huggingface.co/datasets/Kratos-AI/Korean_Price_Tags_Image_Dataset

### 10. Hugging Face - Korean User Manuals Dataset

- 도메인: 사용설명서/매뉴얼
- 성격: 소규모 공개 문서셋
- 규모:
  - 20 rows
  - 약 16.5 MB
- 장점:
  - 인쇄 문서 OCR sanity check에 적합
  - 일부 bilingual 문서도 포함 가능
- 한계:
  - 표준 벤치마크로 보기엔 규모 부족
- 링크:
  - https://huggingface.co/datasets/HumynLabs/Korean_User_Manuals_Dataset

### 11. 상용/구매형 - Nexdata 5,711 Images Korean Handwriting OCR Data

- 도메인: 한국어 필기 OCR
- 성격: 상용셋
- 규모:
  - 5,711 images
- 라벨:
  - line-level quadrilateral box
  - transcription
- 장점:
  - 필기 라인 단위 OCR 평가에 적합
  - GitHub 데모 저장소가 있어 형식을 미리 확인 가능
- 주의:
  - 상용 라이선스
- 링크:
  - GitHub 데모: https://github.com/Nexdata-AI/5711-Images-Korean-Handwriting-OCR-data
  - 판매 페이지 안내는 README에 연결됨

### 12. 상용/구매형 - K-DATA Large Handwriting OCR Data

- 도메인: 대규모 필기 OCR
- 성격: 상용셋
- 공개 확인 내용:
  - 판매 페이지 기준 상품명 `Large Handwriting OCR Data`
- 장점:
  - 대규모 필기 데이터가 필요할 때 후보
- 주의:
  - 가격 기반 판매형 데이터셋이라 가볍게 쓰기 어렵다
  - 공개 페이지에서 세부 라벨 구조는 제한적으로만 확인됨
- 링크:
  - https://k-data.kr/product/LargeHandwritingOCRData

## 용도별 추천

### A. 지금 프로젝트에 가장 맞는 평가셋

- `KORIE`
- `AI Hub - 다양한 형태의 한글 문자 OCR`
- `AI Hub - 공공행정문서 OCR`

이 조합이면 `영수증`, `문자/단어`, `실문서`를 모두 커버할 수 있다.

### B. 혼합 스크립트 강건성까지 보고 싶을 때

- `AI Hub - 다중언어 OCR`
- `Korean Price Tags Image Dataset`

### C. 손글씨 성능을 따로 보고 싶을 때

- `AI Hub - 다양한 형태의 한글 문자 OCR`
- `Korean Handwritten Notes Dataset`
- `Nexdata 5,711 Images Korean Handwriting OCR Data`

## 이 프로젝트 관점의 실무 제안

현 저장소의 manifest 포맷은 다음 3종으로 나눠 수집하는 것이 좋다.

1. `word/line recognition`
   - KORIE OCR crops
   - 다양한 형태의 한글 문자 OCR
2. `document OCR`
   - 공공행정문서 OCR
   - 교육/금융·물류 OCR
3. `mixed-script robustness`
   - 다중언어 OCR
   - 가격표/간판류 소규모 공개셋

권장 우선순위는 아래와 같다.

1. KORIE를 유지
2. AI Hub `다양한 형태의 한글 문자 OCR` 추가
3. AI Hub `공공행정문서 OCR` 추가
4. 필요 시 `다중언어 OCR` 추가
5. 공개 Hugging Face 소규모셋은 smoke test 전용으로만 사용

## 조사 메모

- AI Hub 데이터는 플랫폼 특성상 로그인/신청 절차가 필요한 경우가 많다.
- `공공행정문서 OCR` 페이지에는 `내국인만 데이터 신청 가능`이 명시되어 있었다.
- `OCR 데이터(교육)`, `OCR 데이터(금융 및 물류)`는 이번 조사에서 AI Hub 메인 목록 노출은 확인했지만 상세 페이지 ID까지는 즉시 확인하지 못했다.
- `KORIE`는 논문과 GitHub 저장소 간 초기 공개 수량이 `748`과 `774`로 달라 보인다. 실제 벤치마크 채택 전 release 기준 수치를 통일해야 한다.

## 출처

- KORIE 논문: https://www.mdpi.com/2227-7390/14/1/187
- KORIE GitHub: https://github.com/MahmoudSalah/KORIE
- AI Hub 다양한 형태의 한글 문자 OCR: https://aihub.or.kr/aidata/33987
- AI Hub 공공행정문서 OCR: https://aihub.or.kr/aidata/30724
- AI Hub 다중언어 OCR: https://www.aihub.or.kr/aihubdata/data/view.do?aihubDataSe=data&currMenu=115&dataSetSn=71730&pageIndex=7&srchDetailCnd=DETAILCND001&srchOptnCnd=OPTNCND001&srchOrder=ORDER001&srchPagePer=20&topMenu=100
- AI Hub 메인 목록: https://aihub.or.kr/
- Korean Handwritten Notes Dataset: https://huggingface.co/datasets/HumynLabs/Korean_Handwritten_Notes_Dataset
- Korean Receipts Dataset: https://huggingface.co/datasets/HumynLabs/Korean_Receipts_Dataset
- Korean Price Tags Image Dataset: https://huggingface.co/datasets/Kratos-AI/Korean_Price_Tags_Image_Dataset
- Korean User Manuals Dataset: https://huggingface.co/datasets/HumynLabs/Korean_User_Manuals_Dataset
- Nexdata handwriting dataset demo: https://github.com/Nexdata-AI/5711-Images-Korean-Handwriting-OCR-data
- K-DATA Large Handwriting OCR Data: https://k-data.kr/product/LargeHandwritingOCRData
