import streamlit as st
 
st.title("Hello, World! 👋")
st.write("Welcome to my first Streamlit app.")
 
name = st.text_input("What's your name?")
if name:
    st.success(f"Hello, {name}! 🎉")