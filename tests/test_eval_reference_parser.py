"""scripts/eval.py의 parse_speaker_sentence_reference 유닛 테스트.

`scripts/`는 패키지가 아니므로 sys.path에 추가해 임포트한다
(tests/test_analyze_case3_hallucination.py와 동일 방식).

fixture는 실제 정답 파일(test_data/*.txt — [spkN] 헤더가 있으면 신형식, 없으면
구형식)의 발췌를 사용해 실제 포맷 특이사항(줄 끝 공백, 말미 빈 줄 등)을 그대로
반영한다.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from eval import parse_speaker_sentence_reference  # noqa: E402

# test_data/ytn2.txt(신형식) 발췌 — 2화자, 화자당 문장 1개, spk1이 비인접 재등장.
YTN2_EXCERPT = """[spk1]
First among those were our efforts to maintain a robust, combined defense posture, and to strengthen coordination towards achieving the final, fully verified denuclearization of North Korea.

[spk2]
논의한 사안 중에서는 우선 왕성한 연합방위태세를 유지하기 위한 노력을 경주하자는 것과 북한의 최종적 그리고 완전히 검증된 비핵화를 달성하기 위해 협조를 강화하자는 취지의 논의를 했습니다.

[spk1]
In support of these ends, we remain resolute in our enforcement of the United Nations Security Council resolutions.

[spk2]
이런 목표들을 달성하기 위해서 우리는 UN안보리 결의를 집행하는 것과 관련해 저희 변함 없는 입장을 고수하고 있습니다.
"""

# test_data/sbs1.txt(신형식) 발췌 — spk1 블록에 문장 6개(줄 끝 공백 포함, 실제 파일 그대로),
# 뒤이어 spk2 블록에 문장 1개.
SBS1_EXCERPT = """[spk1]
현지 시간 5일 미국 육군 전쟁 대학 강연에 나선 제이비어 브런슨 주한미군 사령관.

자신의 소셜 미디어 X의 강연 사진과 함께 한반도 동쪽이 위를 향하게 뒤집어 놓은 지도를 올렸습니다.

브런슨 사령관은 관점이 바뀌면 지리적 의미도 완전히 달라진다고 강조했습니다.

지도를 돌려보면 태평양은 텅 빈 바다가 아니라 동맹국들이 연결된 거대한 방어선이라는 겁니다.

특히 한국을 콕 집어 인도 태평양에 미국의 힘을 고정하는 영구적인 지상 플랫폼이라고 정의했습니다.

지난해에도 브론슨 사령관은 한반도의 지정학적 가치를 항공모함에 비유한 바 있습니다.

[spk2]
From a satellite image, the Republic of Korea looks like an island, or like a fixed aircraft carrier floating in the water between Japan and mainland China.
"""

# test_data/bong1.txt(신형식) 발췌 — 4화자 spk1~spk4, spk1/spk3/spk4가 비인접 재등장,
# 단일/복수 문장 블록 혼재, 한/영 혼재.
BONG1_EXCERPT = """[spk1]
Song, when you read the screenplay for the first time, what did you think?

[spk4]
누가 주인공일까 이런 생각을 제가 제일 많이 했어요.

[spk3]
The thought that I had the most is who is the main protagonist.

[spk4]
그래서 저 돌 들고 있는 저 아들놈이 아주 근소한 차이로 저보다 분량이 조금 더 많은데 자기가 주인공이라고 막 떠들고 지금 돌아다니고 있는데 영화 보셔서 아시겠지만 누가 주인공 제가 주인공 맞죠?

[spk3]
So my son who is holding up the rock over there has a little bit more screen time than I do in the film.

So he's been going around saying that he's the main character, main protagonist.

But you all seen the film.

Who is the main protagonist? it's him.

[spk2]
This man.

[spk1]
So, the rock what was the What's the metaphor?

What's the significance of the rock that keeps popping up?
"""

# 구형식(빈 줄 구분, [spkN] 헤더 없음) 예시 — 구형식 단독 파일은 더 이상 test_data/에 존재하지
# 않으나(현재는 test_data/*.txt 하나로 통합), 폴백 분기 검증을 위해 합성한 발췌.
OLD_FORMAT_EXCERPT = """First among those were our efforts to maintain a robust, combined defense posture, and to strengthen coordination towards achieving the final, fully verified denuclearization of North Korea.

논의한 사안 중에서는 우선 왕성한 연합방위태세를 유지하기 위한 노력을 경주하자는 것과 북한의 최종적 그리고 완전히 검증된 비핵화를 달성하기 위해 협조를 강화하자는 취지의 논의를 했습니다.

In support of these ends, we remain resolute in our enforcement of the United Nations Security Council resolutions.
"""

# test_data/bong1_speak,sentence_sperate.txt 말미 발췌(spk2 2문장 + spk3 3문장) + 의도적으로 덧붙인
# 말미 빈 줄·공백(원본에도 말미 빈 줄이 있으나, 여기서는 엣지케이스를 명확히 하기 위해 더 강하게 부여).
BONG1_TAIL_EXCERPT_WITH_TRAILING_JUNK = """[spk2]
주인공이 그러잖아요. 메타포리칼하다고. 주인공이 저기 주인공이 아니구나 참. 아틀렘이가? 죄송합니다 형님. 들고서 메타포리칼하다고 하잖아요.

그래서 그 보통은 이제 스쿼트 당신처럼 이제 기자나 평론가분들이 영화를 보고나서 상징적이다 이렇게 말하는 건데 극 중 인물이 지가 지 입으로 상징적이다 라고 하고 자빠졌는데.

[spk3]
So i'll give you guys the brief context where they were laughing.

Director Bong tried to explain the line from the son called him the main character and apologized Song over here for calling him the main character.

But the director Bong was saying, as you know, you have the son the main son character say within the film this is so metaphorical and usually that's something that reporters or critics say when discussing the metaphor of the film but here you have the caracter announcing it on screen.



"""


def test_two_speaker_single_sentence_per_block():
    """ytn2 형태: 화자당 문장 1개, spk1이 비인접(0, 2번 인덱스) 재등장해도 블록이 병합되지 않는다."""
    result = parse_speaker_sentence_reference(YTN2_EXCERPT)
    assert result is not None
    assert [b["speaker"] for b in result["blocks"]] == ["spk1", "spk2", "spk1", "spk2"]
    assert result["blocks"][0]["sentences"] == [
        "First among those were our efforts to maintain a robust, combined defense posture, and "
        "to strengthen coordination towards achieving the final, fully verified denuclearization of North Korea."
    ]
    assert result["blocks"][1]["sentences"] == [
        "논의한 사안 중에서는 우선 왕성한 연합방위태세를 유지하기 위한 노력을 경주하자는 것과 "
        "북한의 최종적 그리고 완전히 검증된 비핵화를 달성하기 위해 협조를 강화하자는 취지의 논의를 했습니다."
    ]
    assert result["blocks"][2]["sentences"] == [
        "In support of these ends, we remain resolute in our enforcement of the United Nations Security Council resolutions."
    ]
    assert result["blocks"][3]["sentences"] == [
        "이런 목표들을 달성하기 위해서 우리는 UN안보리 결의를 집행하는 것과 관련해 저희 변함 없는 입장을 고수하고 있습니다."
    ]


def test_multi_sentence_block():
    """sbs1 형태: spk1 블록 하나에 문장 6개가 순서대로 들어가고, 그 뒤 spk2 블록은 문장 1개."""
    result = parse_speaker_sentence_reference(SBS1_EXCERPT)
    assert result is not None
    assert [b["speaker"] for b in result["blocks"]] == ["spk1", "spk2"]
    spk1_sentences = result["blocks"][0]["sentences"]
    assert len(spk1_sentences) == 6
    assert spk1_sentences[0] == "현지 시간 5일 미국 육군 전쟁 대학 강연에 나선 제이비어 브런슨 주한미군 사령관."
    assert spk1_sentences[1] == "자신의 소셜 미디어 X의 강연 사진과 함께 한반도 동쪽이 위를 향하게 뒤집어 놓은 지도를 올렸습니다."
    assert spk1_sentences[5] == "지난해에도 브론슨 사령관은 한반도의 지정학적 가치를 항공모함에 비유한 바 있습니다."
    # 줄 끝 공백은 strip되어야 한다(원본 파일에 trailing space 존재).
    for s in spk1_sentences:
        assert s == s.strip()
    assert result["blocks"][1]["sentences"] == [
        "From a satellite image, the Republic of Korea looks like an island, or like a fixed aircraft "
        "carrier floating in the water between Japan and mainland China."
    ]


def test_four_speaker_nonadjacent_recurrence():
    """bong1 형태: spk1/spk3/spk4가 비인접 재등장 — 같은 화자 id라도 블록이 절대 병합되지 않는다."""
    result = parse_speaker_sentence_reference(BONG1_EXCERPT)
    assert result is not None
    speakers = [b["speaker"] for b in result["blocks"]]
    assert speakers == ["spk1", "spk4", "spk3", "spk4", "spk3", "spk2", "spk1"]
    # spk1의 두 등장은 서로 다른 블록이며 문장 수가 다르다(1개 vs 2개) — 병합됐다면 3개 블록으로 안 나뉘었을 것.
    assert result["blocks"][0]["sentences"] == [
        "Song, when you read the screenplay for the first time, what did you think?"
    ]
    assert result["blocks"][6]["sentences"] == [
        "So, the rock what was the What's the metaphor?",
        "What's the significance of the rock that keeps popping up?",
    ]
    # spk3의 두 등장도 서로 다른 블록(1문장 vs 4문장), 병합되지 않는다.
    assert result["blocks"][2]["sentences"] == ["The thought that I had the most is who is the main protagonist."]
    assert len(result["blocks"][4]["sentences"]) == 4
    assert result["blocks"][4]["sentences"][0] == (
        "So my son who is holding up the rock over there has a little bit more screen time than I do in the film."
    )
    assert result["blocks"][4]["sentences"][3] == "Who is the main protagonist? it's him."


def test_no_speaker_header_returns_none():
    """[spkN] 헤더가 전혀 없는 구형식 텍스트는 None을 반환해 호출부가 구 파서로 폴백하게 한다."""
    result = parse_speaker_sentence_reference(OLD_FORMAT_EXCERPT)
    assert result is None


def test_trailing_blank_lines_no_spurious_empty_entries():
    """말미 빈 줄·공백이 여러 개 있어도 마지막 블록에 빈 문자열 문장/블록이 생기지 않는다."""
    result = parse_speaker_sentence_reference(BONG1_TAIL_EXCERPT_WITH_TRAILING_JUNK)
    assert result is not None
    assert [b["speaker"] for b in result["blocks"]] == ["spk2", "spk3"]
    last_block = result["blocks"][-1]
    assert last_block["sentences"] == [
        "So i'll give you guys the brief context where they were laughing.",
        "Director Bong tried to explain the line from the son called him the main character and "
        "apologized Song over here for calling him the main character.",
        "But the director Bong was saying, as you know, you have the son the main son character say "
        "within the film this is so metaphorical and usually that's something that reporters or critics "
        "say when discussing the metaphor of the film but here you have the caracter announcing it on screen.",
    ]
    # 어떤 블록에도 빈 문자열 문장이 없어야 한다.
    for block in result["blocks"]:
        assert "" not in block["sentences"]
        assert all(s.strip() for s in block["sentences"])


def test_plain_text_strips_labels_and_matches_sentence_concatenation():
    """plain_text에는 [spkN] 라벨 문자열이 전혀 없고, 전체 문장을 공백으로 이어붙인 것과 일치한다."""
    result = parse_speaker_sentence_reference(BONG1_EXCERPT)
    assert result is not None
    assert "[spk" not in result["plain_text"]
    all_sentences = [s for b in result["blocks"] for s in b["sentences"]]
    assert result["plain_text"] == " ".join(all_sentences)

    # ytn2 fixture로도 동일 계약을 재확인(2번째 실제 파일 형태).
    result2 = parse_speaker_sentence_reference(YTN2_EXCERPT)
    assert result2 is not None
    assert "[spk" not in result2["plain_text"]
    all_sentences2 = [s for b in result2["blocks"] for s in b["sentences"]]
    assert result2["plain_text"] == " ".join(all_sentences2)
