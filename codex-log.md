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

- 실행 계획: 전체 실행 전, 5개 dev / 5개 val 샘플로 optimizer 경로를 smoke validation 한다.
- 이유: OpenAI optimizer 응답 형식과 Ollama OCR 호출을 함께 검증해야 전체 라운드 실패 비용을 줄일 수 있기 때문.

- 실행 계획: smoke run 성공 후 KORIE OCR 공개 manifest 전체(dev 60 / val 100)로 run-all을 실행한다.
- 주의: 이 데이터는 field crop OCR 벤치마크이며, 전체 영수증 OCR은 아님. 현재 공개 데이터 기준 최적화 결과로 기록한다.

- 구현 보완: validation 결과를 본 뒤 PRD의 최종 채택 규칙이 코드에 반영되지 않은 것을 확인.
- 조치: baseline/final validation 집계를 기반으로 adopted prompt를 결정하는 로직과 산출물(adopted_prompt.txt, report 반영)을 추가함.
- 이유: 최적화가 validation에서 실패한 경우 baseline을 채택해야 PRD와 일치하기 때문.

- 새로운 데이터셋 판단: 전체 영수증 OCR용 공개 데이터셋 후보로 CORD를 선택해 확인한다.
- 이유: 전체 receipt image가 있고 공개 접근 가능하며, 현재 KORIE crop split보다 PRD 가정에 더 가깝기 때문.

- CORD 실험 판단: train split rows API가 300MB 제한으로 실패하므로, 우선 first-rows로 안정적으로 가져올 수 있는 train 26 / val 100 구성으로 full-receipt 실험을 수행한다.
- 이유: 사용자 요청은 새 데이터셋으로 동일 실험을 계속 진행하는 것이고, 현재 가장 빠르게 end-to-end 검증 가능한 전체 영수증 경로이기 때문.

- CORD full-run 판단 변경: train 26 / val 100 full receipt run이 추론 시간상 과도하게 길어져 turn 내 완료 가능성이 낮음.
- 조치: full receipt 조건은 유지하되, 실행 가능성을 위해 더 작은 샘플 수로 동일 루프를 완료해 결과를 확보한다.

- full receipt 병목 대응: OCR client에서 이미지를 최대 1600px로 리사이즈 후 JPEG 인코딩하도록 변경.
- 이유: 원본 full receipt 이미지를 그대로 보내면 전송량과 추론 지연이 커져 실험 완료 시간이 과도하게 길어질 수 있기 때문.

- 한국어 공개 OCR 평가셋 판단: 영수증에 한정하지 않고 `한국어 이미지 + 정답 텍스트`가 붙은 공개 데이터셋을 다시 탐색함.
- 확인 결과: `HumynLabs/Korean_Receipts_Dataset`은 한국어 영수증 이미지 20장 공개지만 텍스트 라벨이 보이지 않아 OCR 평가셋으로는 직접 사용 불가. 반면 `AbdullahRian/Korean.OCR.Img.text.pair`는 이미지와 텍스트가 함께 공개되어 바로 OCR 평가용 manifest 생성 가능.
- 고려한 선택지: 영수증 이미지만 우선 수집 / 평가 가능한 텍스트 페어셋 우선 수집 / 둘 다 분리 수집.
- 판단: 둘 다 분리 수집.
- 이유: 사용자는 한국어 이미지면 충분하다고 했고, 동시에 OCR 평가에도 쓰길 원했다. 그래서 `이미지 전용 탐색셋`과 `이미지+텍스트 평가셋`을 각각 모으는 편이 목적에 가장 잘 맞는다.

- Arize 기록 누락 원인 조사: 기존 구현은 `https://app.arize.com/api/v1/space/log`로 집계 JSON을 직접 POST하고 있었음.
- 판단: `Arize AX` 기준 공식 엔드포인트인 `https://api.arize.com/v1/log`와 `Authorization`, `Grpc-Metadata-space_id` 헤더 형식으로 교체함.
- 이유: 사용자 확인 결과 사용 제품은 Phoenix가 아니라 Arize AX였고, 기존 구현은 실패를 삼켜 실제로는 아무 기록도 남지 않는 상태였음.

- KORIE full receipt 재구성 가능성 재검토: 공개 detection split를 실제로 다운로드해 내부 포맷을 확인함.
- 확인 결과: `labels/*.txt`는 클래스 id와 bbox 좌표만 포함하며, 박스별 transcription은 포함하지 않음.
- 판단: 현재 공개 detection split만으로는 full-page OCR reference text를 재구성하지 않음.
- 이유: 좌표 정보만으로는 plain text GT를 만들 수 없고, 이는 사용자가 허용한 느슨한 공백/줄바꿈 평가와는 다른 문제이기 때문. 텍스트 전사 자체가 없음.

- 다른 Codex가 내려받은 `korean-ocr-img-text-pair` split를 현재 loader에 연결하는 과정에서 경로 규칙 충돌이 발생함.
- 확인 결과: `prepare-split` 결과 manifest 일부가 manifest-relative 경로가 아니라 repo-root-relative 경로를 포함하고 있었고, 기존 `load_manifest`는 이를 무조건 manifest 디렉터리에 붙여 잘못된 경로를 만들었음.
- 판단: `load_manifest`에서 `manifest-relative 경로가 존재하면 우선 사용, 아니면 원래 상대경로를 그대로 사용`하는 보정 로직을 추가함.
- 이유: 기존 KORIE/기타 manifest와의 호환성을 깨지 않으면서, 이미 생성된 split manifest도 다시 쓸 수 있게 하는 편이 더 실용적이기 때문.

- `AbdullahRian/Korean.OCR.Img.text.pair` 실험 규모 판단: 60/40 full split로 `run-all`을 시도했으나 샘플 1건 OCR에 약 50초가 걸려 현실적으로 너무 느렸음.
- 고려한 선택지: full split 강행 / OCR client 추가 축소 / mini benchmark 별도 생성.
- 판단: 가장 짧은 line 이미지 위주로 `dev 2 / val 2` mini benchmark를 별도 생성해 경로만 먼저 검증함.
- 결과: seed 최적 prompt는 `P1`, 1라운드 2후보 최적화 후 mini validation에서 baseline과 optimized가 동률(CER 0.3409)로 나옴.
