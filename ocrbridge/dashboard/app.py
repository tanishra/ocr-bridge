# ocrbridge/dashboard/app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json

# Page config
st.set_page_config(
    page_title="OCRBridge - Receipt Processor",
    page_icon="📄",
    layout="wide"
)

# API endpoint
API_URL = "http://localhost:8000"

st.title("📄 OCRBridge - AI Receipt Processor")
st.markdown("Upload receipts (PDF or images) for instant data extraction")

# Sidebar
st.sidebar.header("Settings")
api_url = st.sidebar.text_input("API URL", value=API_URL)

# Main upload area
uploaded_file = st.file_uploader(
    "Drop receipt here",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=False
)

if uploaded_file:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📤 Uploaded File")
        st.write(f"**Filename:** {uploaded_file.name}")
        st.write(f"**Size:** {len(uploaded_file.getvalue()) / 1024:.1f} KB")
        st.write(f"**Type:** {uploaded_file.type}")
        
        # Show preview for images
        if uploaded_file.type.startswith('image'):
            st.image(uploaded_file, use_column_width=True)
        else:
            st.info("PDF preview not available")
    
    with col2:
        st.subheader("⚙️ Processing")
        
        with st.spinner("Extracting data with AI..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                response = requests.post(f"{api_url}/process", files=files, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result["success"]:
                        st.success("✅ Extraction successful!")
                    else:
                        st.warning(f"⚠️ {result['status']}")
                    
                    st.json(result)
                    
                    # Display extracted fields nicely
                    if result["data"] and result["data"]["fields"]:
                        st.subheader("📊 Extracted Data")
                        
                        fields_data = []
                        for field_name, field_info in result["data"]["fields"].items():
                            fields_data.append({
                                "Field": field_name.replace("_", " ").title(),
                                "Value": field_info["value"],
                                "Confidence": f"{field_info['confidence']*100:.1f}%"
                            })
                        
                        df = pd.DataFrame(fields_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Confidence indicator
                        confidence = result["data"]["confidence"]
                        st.progress(confidence, text=f"Overall Confidence: {confidence*100:.1f}%")
                        
                else:
                    st.error(f"❌ API Error: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Cannot connect to API at {api_url}. Is the backend running?")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Batch processing section
st.markdown("---")
st.subheader("📁 Batch Processing")

batch_files = st.file_uploader(
    "Upload multiple receipts",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True,
    key="batch"
)

if batch_files:
    st.write(f"📎 {len(batch_files)} files selected")
    
    if st.button("Process All", type="primary"):
        progress_bar = st.progress(0)
        results = []

        try:
            multipart_files = [
                ("files", (file.name, file.getvalue(), file.type))
                for file in batch_files
            ]
            response = requests.post(f"{api_url}/process-batch", files=multipart_files, timeout=300)

            if response.status_code == 200:
                payload = response.json()
                results = payload.get("results", [])
            elif response.status_code == 404:
                st.warning("Batch endpoint not available, using file-by-file fallback.")
                for idx, file in enumerate(batch_files):
                    try:
                        files = {"file": (file.name, file.getvalue(), file.type)}
                        single = requests.post(f"{api_url}/process", files=files, timeout=180)
                        if single.status_code == 200:
                            item = single.json()
                            item["filename"] = file.name
                            results.append(item)
                        else:
                            results.append({
                                "filename": file.name,
                                "success": False,
                                "status": "failed",
                                "error": single.text
                            })
                    except Exception as e:
                        results.append({
                            "filename": file.name,
                            "success": False,
                            "status": "failed",
                            "error": str(e)
                        })
                    progress_bar.progress((idx + 1) / len(batch_files))
            else:
                st.error(f"❌ Batch API Error: {response.text}")
        except Exception as e:
            st.error(f"❌ Batch processing failed: {str(e)}")

        if results:
            progress_bar.progress(1.0)
        
        # Show results
        st.subheader("Results")
        for r in results:
            if r.get("success"):
                st.success(f"✅ {r.get('filename', 'unknown')}")
            else:
                st.error(f"❌ {r.get('filename', 'unknown')}: {r.get('error', 'Unknown error')}")

# Footer
st.markdown("---")
st.caption("OCRBridge v0.1.0 - Built with FastAPI + Streamlit + Gemini")
