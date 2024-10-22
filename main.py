import streamlit as st

st.title("Stock Data Visualization and Prediction")
st.write("This is a basic Streamlit app to test rendering.")

# Add a simple input and display
user_input = st.text_input("Enter your name", "Guest")
st.write(f"Hello, {user_input}!")

# Add a simple chart
import numpy as np
chart_data = pd.DataFrame(np.random.randn(20, 3), columns=['A', 'B', 'C'])
st.line_chart(chart_data)
