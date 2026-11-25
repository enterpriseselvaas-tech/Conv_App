import streamlit as st
import json
import os
import subprocess
import tempfile
from google import genai
from google.genai import types
from docxtpl import DocxTemplate

st.set_page_config(page_title="KamalaKannan Transport - Invoice Converter", page_icon="🚛", layout="centered")

st.title("🚛 Invoice Template Converter")
st.caption("KamalaKannan Transport → Top Anil Maarketing Company")

TEMPLATE_FILE = "template.docx"

# Sidebar for API Key & Optional Template Override
with st.sidebar:
    st.header("Settings")
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    api_key = st.text_input("Gemini API Key", value=default_key, type="password")
    
    st.divider()
    st.subheader("Template Status")
    if os.path.exists(TEMPLATE_FILE):
        st.success(f"Built-in `{TEMPLATE_FILE}` loaded.")
    else:
        st.warning(f"`{TEMPLATE_FILE}` not found in folder. Upload one below:")
    
    custom_docx = st.file_uploader("Override Template (Optional)", type=["docx"])

# 1. Single PDF Uploader
pdf_file = st.file_uploader("Upload Source Invoice (PDF)", type=["pdf"])

def convert_docx_to_pdf(docx_path, output_dir):
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    base_name = os.path.splitext(os.path.basename(docx_path))
    return os.path.join(output_dir, f"{base_name}.pdf")

# 2. Extract Data Step
if st.button("Extract Invoice Data", type="primary", use_container_width=True):
    if not api_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    elif not pdf_file:
        st.error("Please upload the source Invoice PDF.")
    else:
        try:
            with st.spinner("Reading invoice PDF..."):
                client = genai.Client(api_key=api_key)
                pdf_bytes = pdf_file.read()

                prompt = """
                Extract the transport invoice details from this PDF into a JSON object with these exact keys.
                If any field is missing or not found in the document, set its value to "--".

                Keys:
                - "invoice_no": Invoice number (e.g., "1616/2025-26")
                - "inv_date": Invoice date (e.g., "31-03-2026")
                - "lorry_no": Vehicle/Lorry number (e.g., "TN59CU6937")
                - "mode": Vehicle mode/size (e.g., "20FEET")
                - "from_loc": Origin location (e.g., "DINDIGUL")
                - "to_loc": Destination location (e.g., "POLLACHI")
                - "cust_doc_no": Customer Document Number (e.g., "2025125855")
                - "lr_no": LR Number (e.g., "8420")
                - "loading_date": Loading Date inside the item description (e.g., "31-03-2026")
                - "freight": Base freight amount without currency symbol (e.g., "8000")
                - "qty": Quantity (e.g., "1")
                - "other_charges_desc": Description of other charges if present (e.g., "Unloading Charges"), else "--"
                - "other_chrg_amt": Numeric amount of other charges if present (e.g., "1165"), else "--"
                - "total_amount": Grand total amount (e.g., "9165")
                - "total_in_words": Total amount in words (e.g., "Nine Thousand One Hundred And Sixty Five Rupees Only")
                - "remarks": Any extra notes or remarks if present, else "--"

                Return ONLY valid JSON.
                """

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                raw_data = json.loads(response.text)
                # Ensure any empty/null values default to "--"
                cleaned_data = {
                    k: (str(v).strip() if v is not None and str(v).strip() != "" else "--")
                    for k, v in raw_data.items()
                }
                st.session_state["extracted_data"] = cleaned_data
                st.success("Data extracted! Review or edit below before generating the PDF.")

        except Exception as e:
            st.error(f"Extraction error: {e}")

# 3. Review & Generate PDF Step
if "extracted_data" in st.session_state:
    data = st.session_state["extracted_data"]
    
    with st.form("review_form"):
        st.subheader("Review & Edit Extracted Fields")
        c1, c2 = st.columns(2)
        data["invoice_no"] = c1.text_input("Invoice No", data.get("invoice_no", "--"))
        data["inv_date"] = c2.text_input("Invoice Date", data.get("inv_date", "--"))
        
        c3, c4, c5 = st.columns(3)
        data["lorry_no"] = c3.text_input("Lorry No", data.get("lorry_no", "--"))
        data["mode"] = c4.text_input("Mode", data.get("mode", "--"))
        data["loading_date"] = c5.text_input("Loading Date", data.get("loading_date", "--"))

        c6, c7 = st.columns(2)
        data["from_loc"] = c6.text_input("FROM", data.get("from_loc", "--"))
        data["to_loc"] = c7.text_input("TO", data.get("to_loc", "--"))

        c8, c9 = st.columns(2)
        data["cust_doc_no"] = c8.text_input("Cust. Doc. No", data.get("cust_doc_no", "--"))
        data["lr_no"] = c9.text_input("LR No", data.get("lr_no", "--"))

        c10, c11, c12 = st.columns(3)
        data["freight"] = c10.text_input("Freight (₹)", data.get("freight", "--"))
        data["qty"] = c11.text_input("Qty", data.get("qty", "--"))
        data["other_chrg_amt"] = c12.text_input("Other Charges Amt (₹)", data.get("other_chrg_amt", "--"))

        data["other_charges_desc"] = st.text_input("Other Charges Description", data.get("other_charges_desc", "--"))
        data["total_amount"] = st.text_input("Total Amount (₹)", data.get("total_amount", "--"))
        data["total_in_words"] = st.text_input("Total In Words", data.get("total_in_words", "--"))
        data["remarks"] = st.text_input("Remarks (if any)", data.get("remarks", "--"))

        generate_btn = st.form_submit_button("Generate Final PDF", type="primary", use_container_width=True)

    if generate_btn:
        if not custom_docx and not os.path.exists(TEMPLATE_FILE):
            st.error(f"Missing `{TEMPLATE_FILE}`. Please add it to your app folder or upload it in the sidebar.")
        else:
            # Enforce "--" if user cleared any input box in the form
            final_data = {
                k: (v.strip() if v and v.strip() != "" else "--")
                for k, v in data.items()
            }
            try:
                with st.spinner("Generating PDF..."):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        template_path = os.path.join(tmpdir, "template.docx")
                        filled_docx_path = os.path.join(tmpdir, "filled.docx")

                        if custom_docx:
                            with open(template_path, "wb") as f:
                                f.write(custom_docx.getvalue())
                        else:
                            with open(TEMPLATE_FILE, "rb") as src, open(template_path, "wb") as dst:
                                dst.write(src.read())

                        doc = DocxTemplate(template_path)
                        doc.render(final_data)
                        doc.save(filled_docx_path)

                        final_pdf_path = convert_docx_to_pdf(filled_docx_path, tmpdir)

                        with open(final_pdf_path, "rb") as pdf_out:
                            pdf_bytes_out = pdf_out.read()

                safe_inv_no = final_data["invoice_no"].replace("/", "-")
                if safe_inv_no == "--":
                    safe_inv_no = "Document"

                st.download_button(
                    label=f"⬇️ Download Invoice_{safe_inv_no}.pdf",
                    data=pdf_bytes_out,
                    file_name=f"Invoice_{safe_inv_no}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF Generation error: {e}")
