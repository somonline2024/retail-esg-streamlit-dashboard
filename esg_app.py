"""
Streamlit-based Retail Stock Management Dashboard
Converted from the provided React App.jsx to a single-file Streamlit app.

Features included:
- Manual inventory add (name, daily_sales, shelf_life_days, base_price, stock, demand_score)
- CSV upload with parsing and adding to inventory
- CSV template download
- Inventory listing and delete
- Simple analytics (stock bar chart, demand bar chart, pie chart for top items)
- AI Assistant: sends message + inventory + locations to backend `/assistant`
- Image detection: uploads image to backend `/detect`

How to run:
1. Install dependencies: pip install streamlit pandas plotly requests
2. Run: streamlit run streamlit_app.py

Note: This app expects the same backend API endpoints as the original React app (API_BASE variable).
If you don't have a backend available, the AI and detection features will show errors but the local inventory/CSV functionality will still work.
"""

import streamlit as st
import pandas as pd
import io
import json
import time
import requests
import plotly.express as px
from typing import List, Dict

API_BASE = "https://retail-esg-backend.onrender.com"  # change if needed

# --- Helper utilities -----------------------------------------------------------------

def init_session_state():
    if 'inventory' not in st.session_state:
        st.session_state.inventory = []
    if 'locations' not in st.session_state:
        st.session_state.locations = [
            { 'name': 'Warehouse', 'lat': 22.5726, 'lon': 88.3639 },
            { 'name': 'NGO A', 'lat': 22.589, 'lon': 88.408 }
        ]
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'analytics_data' not in st.session_state:
        st.session_state.analytics_data = None


def parse_daily_sales(s: str) -> List[float]:
    if not s:
        return []
    # accept comma or semicolon separated
    parts = [p.strip() for p in s.replace(';', ',').split(',')]
    nums = []
    for p in parts:
        try:
            if p == '':
                continue
            nums.append(float(p))
        except Exception:
            continue
    return nums


def make_new_item(form: Dict) -> Dict:
    ds_array = parse_daily_sales(form.get('daily_sales', ''))
    return {
        'id': int(time.time() * 1000),
        'name': form.get('name', '').strip(),
        'daily_sales': ','.join([str(int(x)) if float(x).is_integer() else str(x) for x in ds_array]),
        'daily_sales_array': ds_array,
        'shelf_life_days': int(form.get('shelf_life_days', 7)),
        'base_price': float(form.get('base_price', 0) or 0),
        'stock': int(form.get('stock', 0) or 0),
        'demand_score': float(form.get('demand_score', 0.5) or 0.5)
    }


def csv_to_items(file_bytes: bytes) -> List[Dict]:
    # Accept a CSV with columns: name,daily_sales,shelf_life_days,base_price,stock,demand_score
    df = pd.read_csv(io.BytesIO(file_bytes))
    items = []
    for _, row in df.iterrows():
        daily = row.get('daily_sales', '')
        # allow both ; and , separators, and lists
        if isinstance(daily, str) and ('[' in daily and ']' in daily):
            # possible JSON list
            try:
                daily_arr = json.loads(daily)
            except Exception:
                daily_arr = parse_daily_sales(daily)
        elif pd.isna(daily):
            daily_arr = []
        elif isinstance(daily, str) and (';' in daily or ',' in daily):
            daily_arr = parse_daily_sales(daily)
        elif isinstance(daily, list):
            daily_arr = [float(x) for x in daily]
        else:
            # single numeric value
            try:
                daily_arr = [float(daily)]
            except Exception:
                daily_arr = []

        item = {
            'id': int(time.time() * 1000) + len(items),
            'name': str(row.get('name', '')).strip(),
            'daily_sales': ';'.join([str(x) for x in daily_arr]) if daily_arr else '',
            'daily_sales_array': daily_arr,
            'shelf_life_days': int(row.get('shelf_life_days', 7) or 7),
            'base_price': float(row.get('base_price', 0) or 0),
            'stock': int(row.get('stock', 0) or 0),
            'demand_score': float(row.get('demand_score', 0.5) or 0.5)
        }
        items.append(item)
    return items


def download_template_bytes() -> bytes:
    template = (
        "name,daily_sales,shelf_life_days,base_price,stock,demand_score\n"
        "milk,10;12;8;15;9;11;10,7,50,100,0.7\n"
        "bread,30;28;35;40;38;36;37,3,40,200,0.4\n"
        "eggs,20;22;18;25;21;23,14,60,150,0.8\n"
    )
    return template.encode('utf-8')


# --- UI -------------------------------------------------------------------------------

st.set_page_config(page_title='Retail Stock Management', layout='wide')
init_session_state()

st.title('Retail Stock Management System')
st.write('Smart Inventory & AI Analytics (Streamlit port)')

col1, col2 = st.columns([2, 1])

with col1:
    st.header('Upload Inventory')
    # CSV template download
    st.download_button('Download CSV Template', data=download_template_bytes(), file_name='inventory_template.csv', mime='text/csv')

    uploaded_file = st.file_uploader('Upload CSV (columns: name,daily_sales,shelf_life_days,base_price,stock,demand_score)', type=['csv'])
    if uploaded_file is not None:
        try:
            raw = uploaded_file.read()
            items = csv_to_items(raw)
            st.session_state.inventory.extend(items)
            st.success(f'Imported {len(items)} items from CSV')
            #st.experimental_rerun()
            st.rerun()
        except Exception as e:
            st.error('Failed to parse CSV: ' + str(e))

    st.markdown('---')

    st.subheader('Add item manually')
    with st.form('add_item_form'):
        name = st.text_input('Item name')
        daily_sales = st.text_input('Daily sales (e.g., 10,12,15 or 10;12;15)')
        shelf_life_days = st.number_input('Shelf life (days)', value=7, min_value=0)
        base_price = st.number_input('Base price', value=0.0, format='%f')
        stock = st.number_input('Stock quantity', value=0, min_value=0)
        demand_score = st.slider('Demand score (0-1)', min_value=0.0, max_value=1.0, value=0.5, step=0.01)
        submitted = st.form_submit_button('Add to Inventory')
        if submitted:
            form = {
                'name': name,
                'daily_sales': daily_sales,
                'shelf_life_days': shelf_life_days,
                'base_price': base_price,
                'stock': stock,
                'demand_score': demand_score
            }
            new_item = make_new_item(form)
            if new_item['name']:
                st.session_state.inventory.append(new_item)
                st.success(f"Added '{new_item['name']}' to inventory")
                st.experimental_rerun()
            else:
                st.warning('Please provide an item name')

    st.markdown('---')

    # Inventory analytics
    st.header('Inventory Analytics')
    inv = pd.DataFrame(st.session_state.inventory)
    if inv.empty:
        st.info('No items yet — add via CSV or the form.')
    else:
        # Stock bar chart (top 10)
        df_stock = inv[['name', 'stock']].sort_values('stock', ascending=False).head(10)
        fig_stock = px.bar(df_stock, x='name', y='stock', title='Top items by stock')
        st.plotly_chart(fig_stock, use_container_width=True)

        # Demand bar chart
        inv['demand_pct'] = (inv['demand_score'] * 100).astype(float)
        df_demand = inv[['name', 'demand_pct']].sort_values('demand_pct', ascending=False).head(10)
        fig_demand = px.bar(df_demand, x='name', y='demand_pct', title='Demand score (%)')
        st.plotly_chart(fig_demand, use_container_width=True)

        # Pie chart for stock distribution (top 6)
        df_pie = df_stock.copy()
        fig_pie = px.pie(df_pie, names='name', values='stock', title='Stock distribution (top 10)')
        st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.header('AI Assistant')
    st.write('Send a message to the backend assistant (requires backend).')
    user_msg = st.text_input('Ask me anything...', key='assistant_input')
    if st.button('Send to Assistant'):
        if user_msg and user_msg.strip():
            st.session_state.chat_messages.append({'role': 'user', 'content': user_msg})
            payload = {
                'message': user_msg,
                'inventory': st.session_state.inventory,
                'locations': st.session_state.locations
            }
            try:
                with st.spinner('Contacting assistant...'):
                    r = requests.post(f"{API_BASE}/assistant", json=payload, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    assistant_reply = data.get('assistant_reply') or data.get('natural_response') or 'Response received'
                    st.session_state.chat_messages.append({'role': 'assistant', 'content': assistant_reply, 'data': data.get('data')})
                    st.success('Received reply')
            except Exception as e:
                st.session_state.chat_messages.append({'role': 'assistant', 'content': f'Error: {e}', 'error': True})

    st.markdown('### Conversation')
    for msg in st.session_state.chat_messages[-12:][::-1]:
        if msg['role'] == 'user':
            st.markdown(f"**You:** {msg['content']}")
        else:
            if msg.get('error'):
                st.error(msg['content'])
            else:
                st.markdown(f"**Assistant:** {msg['content']}")
                if msg.get('data'):
                    if st.checkbox('Show raw data for latest assistant reply', key=f"raw_{len(st.session_state.chat_messages)}"):
                        st.json(msg['data'])

    st.markdown('---')
    st.header('Image Detection')
    uploaded_image = st.file_uploader('Upload an image for detection', type=['png', 'jpg', 'jpeg'])
    if uploaded_image is not None:
        st.image(uploaded_image, caption='Preview', use_column_width=True)
        if st.button('Analyze Image'):
            try:
                files = {'image': (uploaded_image.name, uploaded_image.getvalue(), uploaded_image.type)}
                with st.spinner('Analyzing...'):
                    r = requests.post(f"{API_BASE}/detect", files=files, timeout=60)
                    r.raise_for_status()
                    d = r.json()
                    st.success('Analysis complete')
                    if d.get('summary'):
                        st.markdown('**Summary**')
                        st.write(d.get('summary'))
                    if d.get('items_detected'):
                        st.markdown('**Items Detected**')
                        for it in d.get('items_detected'):
                            st.write(f"- {it.get('item')} — confidence: {it.get('confidence')}")
            except Exception as e:
                st.error('Detection failed: ' + str(e))


# --- Inventory list / management -------------------------------------------------------

st.markdown('---')
st.header('Live Inventory')

if not st.session_state.inventory:
    st.info('Inventory is empty — add items above.')
else:
    inv_df = pd.DataFrame(st.session_state.inventory)
    # show limited columns
    show_df = inv_df[['id', 'name', 'stock', 'base_price', 'shelf_life_days', 'demand_score', 'daily_sales']]
    st.dataframe(show_df.sort_values('name'))

    # Delete an item
    st.subheader('Remove an item')
    names = [it['name'] for it in st.session_state.inventory]
    to_delete = st.selectbox('Select item to delete', options=[''] + names)
    if st.button('Delete item'):
        if to_delete:
            st.session_state.inventory = [it for it in st.session_state.inventory if it['name'] != to_delete]
            st.success(f"Deleted {to_delete}")
            st.experimental_rerun()
        else:
            st.warning('Please select an item to delete')


# --- Footer / debugging ----------------------------------------------------------------

st.markdown('---')
st.caption('Streamlit port of the React Retail Stock Management dashboard. Backend endpoints used: /assistant and /detect')
