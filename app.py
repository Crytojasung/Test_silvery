"""쇼핑 리스트 앱 (Streamlit)

장을 보기 전/보는 중에 살 물건을 추가·수정·삭제하고 구매 완료를 체크하는 단일 페이지 앱.
데이터는 세션에만 보관하며 브라우저를 새로 고치면 초기화된다(PRD 4.2 참조).

실행: streamlit run app.py
"""

import html

import streamlit as st

# ---------------------------------------------------------------- 페이지 설정
st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

# 완료된 항목 이름에 적용할 스타일.
# 고정 회색 하나로는 라이트/다크 양쪽에서 WCAG AA(4.5:1)를 동시에 만족시킬 수 없어,
# 테마의 본문 색(currentColor)을 흐려서 쓴다. 첫 color 선언은 color-mix 미지원 브라우저용 폴백.
DONE_NAME_STYLE = (
    "color:#6e7781;"
    "color:color-mix(in srgb, currentColor 75%, transparent);"
    "text-decoration:line-through"
)


# ---------------------------------------------------------------- 상태 초기화
def init_state():
    """세션 상태를 초기화한다. 앱 실행 중 한 번만 값을 채운다.

    세션 값은 반드시 st.session_state["키"] 형태로 읽는다.
    "items"는 st.session_state의 메서드 이름과 겹쳐서, 속성 접근(.items)으로 읽으면
    저장한 리스트가 아니라 메서드가 돌아온다.
    """
    if "items" not in st.session_state:
        # 각 항목: {"id": int, "name": str, "qty": int, "checked": bool}
        st.session_state["items"] = []
    if "next_id" not in st.session_state:
        # 항목 id 부여용 카운터. 위젯 key가 id에 묶여 있으므로 값을 되돌리지 않는다.
        st.session_state["next_id"] = 1
    if "editing_id" not in st.session_state:
        # 현재 편집 중인 항목의 id. 편집 중이 아니면 None. (동시에 한 항목만 편집)
        st.session_state["editing_id"] = None
    if "confirm_clear" not in st.session_state:
        # 전체 삭제 확인 단계를 보여줄지 여부
        st.session_state["confirm_clear"] = False

    # 확인 UI는 목록이 있을 때만 렌더되므로, 목록이 비면 플래그를 여기서 정규화한다.
    # (확인 상태에서 항목을 모두 개별 삭제하면 플래그가 남아 경고가 되살아난다)
    if not st.session_state["items"]:
        st.session_state["confirm_clear"] = False


# ------------------------------------------------------------------ 동작 함수
def counts():
    """(전체 개수, 완료 개수)를 현재 상태에서 계산한다. (FR-6)"""
    items = st.session_state["items"]
    return len(items), sum(1 for i in items if i["checked"])


def find_item(item_id):
    """id로 항목을 찾는다. 리스트 인덱스로 찾으면 삭제 후 어긋나므로 항상 id를 쓴다."""
    for item in st.session_state["items"]:
        if item["id"] == item_id:
            return item
    return None


def normalize_qty(qty):
    """수량을 1 이상의 정수로 맞춘다. 위젯 제약과 별개로 저장 값을 보장한다."""
    return max(1, int(round(float(qty))))


def add_item(name, qty):
    """아이템을 목록 맨 아래에 추가한다. 이름이 비어 있으면 False를 반환한다. (FR-1)"""
    name = name.strip()
    if not name:
        return False
    # 같은 이름의 중복 추가는 의도적으로 허용한다.
    st.session_state["items"].append(
        {
            "id": st.session_state["next_id"],
            "name": name,
            "qty": normalize_qty(qty),
            "checked": False,
        }
    )
    st.session_state["next_id"] += 1
    return True


def toggle_item(item_id):
    """체크박스 위젯의 현재 값을 항목 상태에 반영한다. (FR-3)

    key를 지정한 위젯의 value는 최초 렌더에만 적용되므로,
    on_change 콜백에서 위젯 값을 읽어 items와 동기화한다.
    """
    item = find_item(item_id)
    if item is not None:
        item["checked"] = st.session_state[f"chk_{item_id}"]


def save_item(item_id, name, qty):
    """편집 내용을 저장하고 편집 모드를 종료한다. 이름이 비면 False. (FR-4)"""
    name = name.strip()
    if not name:
        return False
    item = find_item(item_id)
    if item is not None:
        item["name"] = name
        item["qty"] = normalize_qty(qty)
    st.session_state["editing_id"] = None
    return True


def clear_editing_if_gone():
    """편집 중이던 항목이 목록에서 사라졌으면 편집 모드를 정리한다."""
    editing_id = st.session_state["editing_id"]
    if editing_id is not None and find_item(editing_id) is None:
        st.session_state["editing_id"] = None


def delete_item(item_id):
    """항목 하나를 삭제한다. (FR-5)"""
    st.session_state["items"] = [
        i for i in st.session_state["items"] if i["id"] != item_id
    ]
    clear_editing_if_gone()


def delete_checked():
    """체크된 항목을 일괄 삭제한다. (FR-5)"""
    st.session_state["items"] = [
        i for i in st.session_state["items"] if not i["checked"]
    ]
    clear_editing_if_gone()


def delete_all():
    """모든 항목을 삭제한다. (FR-5)"""
    st.session_state["items"] = []
    st.session_state["editing_id"] = None
    st.session_state["confirm_clear"] = False


def render_name(item):
    """항목 이름을 표시용 HTML로 만든다.

    unsafe_allow_html으로 출력하므로 사용자 입력은 반드시 이스케이프한다.
    체크된 항목은 취소선 + 회색으로 흐리게 보여준다.
    """
    safe = html.escape(item["name"])
    if item["checked"]:
        return f"<span style='{DONE_NAME_STYLE}'>{safe}</span>"
    return f"<span>{safe}</span>"


# ----------------------------------------------------------------------- 화면
init_state()

st.title("🛒 쇼핑 리스트")

# 요약은 제목 바로 아래에 보이지만, 값은 이번 실행의 상태 변경이 모두 끝난 뒤 채운다. (FR-6)
summary_slot = st.empty()

# --- 아이템 추가 (FR-1)
# 폼으로 감싸면 제출 후 입력창이 자동으로 비워진다.
with st.form("add_form", clear_on_submit=True):
    col_name, col_qty, col_btn = st.columns([0.55, 0.2, 0.25])
    with col_name:
        new_name = st.text_input(
            "아이템 이름", placeholder="예: 우유", label_visibility="collapsed"
        )
    with col_qty:
        new_qty = st.number_input(
            "수량", min_value=1, step=1, value=1, label_visibility="collapsed"
        )
    with col_btn:
        submitted = st.form_submit_button("추가", use_container_width=True)

if submitted:
    if add_item(new_name, new_qty):
        st.rerun()
    else:
        # 검증 실패 경로에서는 rerun하지 않고 경고만 표시한다.
        st.warning("아이템 이름을 입력해 주세요.")

st.divider()

# --- 아이템 목록 (FR-2 ~ FR-5)
if not st.session_state["items"]:
    st.info("목록이 비어 있습니다. 위에서 아이템을 추가해 보세요.")
else:
    for item in st.session_state["items"]:
        item_id = item["id"]

        if st.session_state["editing_id"] == item_id:
            # 편집 모드 (FR-4)
            # 첫 컬럼은 표시 모드의 체크박스 자리를 비워 두는 것이고, 누적 폭(0.08+0.38+0.17)이
            # 표시 모드(0.08+0.42+0.13)와 같아서 입력창 시작점과 버튼 위치가 행마다 어긋나지 않는다.
            _, c1, c2, c3, c4 = st.columns([0.08, 0.38, 0.17, 0.185, 0.185])
            with c1:
                edit_name = st.text_input(
                    "이름", value=item["name"], key=f"edit_name_{item_id}",
                    placeholder="아이템 이름", label_visibility="collapsed",
                )
            with c2:
                edit_qty = st.number_input(
                    "수량", min_value=1, step=1, value=item["qty"],
                    key=f"edit_qty_{item_id}", label_visibility="collapsed",
                )
            with c3:
                if st.button("저장", key=f"save_{item_id}", use_container_width=True):
                    if save_item(item_id, edit_name, edit_qty):
                        st.rerun()
                    else:
                        st.warning("아이템 이름은 비워 둘 수 없습니다.")
            with c4:
                if st.button("취소", key=f"cancel_{item_id}", use_container_width=True):
                    # 변경 내용은 반영하지 않고 편집 모드만 종료
                    st.session_state["editing_id"] = None
                    st.rerun()
        else:
            # 표시 모드 (FR-2)
            c0, c1, c2, c3, c4 = st.columns([0.08, 0.42, 0.13, 0.185, 0.185])
            with c0:
                # 체크 토글은 콜백이 리런을 유발하므로 st.rerun()을 부르지 않는다. (FR-3)
                st.checkbox(
                    "완료", value=item["checked"], key=f"chk_{item_id}",
                    on_change=toggle_item, args=(item_id,),
                    label_visibility="collapsed",
                )
            with c1:
                st.markdown(render_name(item), unsafe_allow_html=True)
            with c2:
                st.markdown(f"`x{item['qty']}`")
            with c3:
                if st.button("수정", key=f"edit_{item_id}", use_container_width=True):
                    st.session_state["editing_id"] = item_id
                    st.rerun()
            with c4:
                if st.button("삭제", key=f"del_{item_id}", use_container_width=True):
                    delete_item(item_id)
                    st.rerun()

    st.divider()

    # --- 일괄 삭제 (FR-5)
    b1, b2 = st.columns(2)
    with b1:
        if st.button(
            "체크된 항목 삭제", disabled=(counts()[1] == 0), use_container_width=True
        ):
            delete_checked()
            st.rerun()
    with b2:
        if st.button("전체 삭제", use_container_width=True):
            st.session_state["confirm_clear"] = True

    if st.session_state["confirm_clear"]:
        st.warning("모든 아이템을 삭제할까요? 되돌릴 수 없습니다.")
        y, n = st.columns(2)
        with y:
            if st.button(
                "네, 전체 삭제", key="do_clear", type="primary",
                use_container_width=True,
            ):
                delete_all()
                st.rerun()
        with n:
            if st.button("아니요", key="cancel_clear", use_container_width=True):
                st.session_state["confirm_clear"] = False
                st.rerun()

# --- 요약 채우기 (이번 실행의 상태 변경이 모두 끝난 뒤)
total, done = counts()
summary_slot.caption(f"전체 {total}개 · 완료 {done}개 · 남음 {total - done}개")
