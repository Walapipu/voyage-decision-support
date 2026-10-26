"""Local prototype profile state, explicitly not an authentication system."""
import streamlit as st


def toggle_theme():
    st.session_state.dark_mode = not st.session_state.get("dark_mode", True)


def logout():
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.logged_out = True


def close_profile():
    st.session_state.edit_profile = False


@st.dialog("Profile settings", on_dismiss=close_profile)
def profile_settings():
    st.caption("Set the name and role shown in your workspace for this session.")
    with st.form("profile_form"):
        name = st.text_input("Display name", value=st.session_state.get("profile_name", "Yi Heng"), max_chars=60)
        role = st.text_input("Role", value=st.session_state.get("profile_role", "Freight planner"), max_chars=80)
        save = st.form_submit_button("Save profile")
    if save:
        if not name.strip():
            st.error("Enter a display name.")
        else:
            st.session_state.profile_name = name.strip()
            st.session_state.profile_role = role.strip()
            st.session_state.edit_profile = False
            st.rerun()


def profile_menu():
    with st.popover(st.session_state.get("profile_name", "Yi Heng"), icon=":material/account_circle:", key="profile_menu", width="stretch"):
        st.write(st.session_state.get("profile_role", "Freight planner"))
        if st.button("Profile settings", icon=":material/manage_accounts:", width="stretch"):
            st.session_state.edit_profile = True
        st.button("Log out", icon=":material/logout:", on_click=logout, width="stretch")
        st.caption("Ends this session and clears its conversation.")
    if st.session_state.get("edit_profile"):
        profile_settings()
