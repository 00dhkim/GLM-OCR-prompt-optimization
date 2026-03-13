# Codex Log

## 2026-03-13

### 초기 구현 판단

- 판단해야 하는 것: 저장소가 비어 있는 상태에서 어떤 기술 스택으로 PRD 전체를 구현할지.
- 고려한 선택지: Python + CLI / Node.js + CLI.
- 판단: Python + `uv` 기반으로 구현.
- 이유: 로컬 OCR 실험, JSONL/CSV 기반 실험 로깅, OpenAI SDK 연동, 테스트 자동화까지 가장 짧은 경로이기 때문.

- 판단해야 하는 것: Ollama 서빙과 optimizer 호출을 어떤 클라이언트로 통일할지.
- 고려한 선택지: Ollama 전용 클라이언트와 OpenAI SDK를 분리 / OpenAI SDK 하나로 통일.
- 판단: OpenAI SDK 하나로 통일.
- 이유: Ollama의 OpenAI-compatible endpoint를 그대로 사용할 수 있어 설정과 호출 표면적을 줄일 수 있기 때문.

- 판단해야 하는 것: Arize를 필수 경로로 둘지 여부.
- 고려한 선택지: 필수 의존성으로 고정 / 선택적 로깅 통합으로 처리.
- 판단: 선택적 로깅 통합으로 처리.
- 이유: PRD에서 Arize를 필수 의존성으로 두지 않았고, 핵심 실험 루프가 외부 SaaS 상태에 종속되면 전체 자동화가 약해지기 때문.

- 판단해야 하는 것: KORIE 입력 포맷이 저장소에 아직 없는 상태에서 데이터 계약을 어떻게 고정할지.
- 고려한 선택지: CSV / 폴더 스캔 기반 / JSONL manifest.
- 판단: JSONL manifest를 표준 입력 계약으로 고정.
- 이유: 샘플별 메타데이터, split, reference text를 같이 담기 쉽고 실험 로그와도 대칭 구조를 만들 수 있기 때문.

- 판단해야 하는 것: KORIE가 실제로 공개 접근 가능한지 여부.
- 고려한 선택지: 논문 기반 추정만 유지 / 공식 GitHub 저장소 확인 후 사용.
- 판단: 공식 GitHub 저장소 공개 확인 후 즉시 로컬로 반입.
- 이유: 사용자 요청이 다운로드 및 실사용까지 포함하고 있고, 공개 접근이 확인되면 더 이상 대기할 이유가 없기 때문.

- 판단해야 하는 것: KORIE 저장소만 사용할지, README의 외부 OCR split 아카이브까지 포함할지 여부.
- 고려한 선택지: 저장소 샘플만 사용 / README에 명시된 OCR split 전체를 내려받아 사용.
- 판단: OCR split 전체를 내려받아 사용.
- 이유: 샘플 2장으로는 PRD의 개발셋과 검증셋 절차를 충족할 수 없고, 사용자도 실제로 다운로드해 이용하라고 명시했기 때문.

- 판단해야 하는 것: 다운로드된 KORIE OCR split가 PRD 가정처럼 전체 영수증 OCR용인지 여부.
- 확인 결과: 공개 OCR split는 전체 영수증이 아니라 필드/단어 crop 이미지와 txt 정답으로 구성됨.
- 고려한 선택지: 공개 데이터 사용을 보류 / 현재 공개 OCR split를 우선 연결하고, 전체 영수증 실험은 별도 데이터 확보 전까지 후속으로 둠.
- 판단: 공개 OCR split를 우선 연결.
- 이유: 사용자 지시가 즉시 다운로드 및 활용이었고, 현재 공개 접근 가능한 정답 라벨 OCR 데이터는 이 경로이기 때문. 이 판단은 나중에 사용자가 전체 영수증 데이터로 교체 여부를 결정할 수 있도록 기록함.

- 판단해야 하는 것: Ollama OpenAI-compatible 비전 입력을 로컬 파일 URI로 줄지, data URL로 줄지 여부.
- 고려한 선택지: `file://` URI / base64 data URL.
- 판단: base64 data URL.
- 이유: Ollama OpenAI-compatible 구현에서 로컬 파일 URI 지원이 불안정할 수 있고, data URL이 더 이식성이 높기 때문.

- 확인 기록: `data/manifests/korie-ocr/one.jsonl` 1건으로 seed smoke run을 실행함.
- 결과: `P0` 기준 CER 0.0000으로 경로가 정상 동작함.
- 의미: 현재 코드 기준으로 `manifest -> Ollama GLM-OCR -> 평가/로그 저장` 흐름이 실제 실행 가능함을 확인.
