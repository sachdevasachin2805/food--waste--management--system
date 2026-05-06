# app.py - Complete Optimized Food Wastage Management System for Hugging Face Spaces
import os
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
matplotlib.use('Agg')

import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from contextlib import contextmanager
import time
import logging
import warnings
import numpy as np
warnings.filterwarnings('ignore')

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Food Wastage Management System",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem;
    }
    .success-metric {
        background: linear-gradient(90deg, #56ab2f 0%, #a8e6cf 100%);
    }
    .warning-metric {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stSelectbox > div > div > select {
        background-color: #f0f2f6;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Improved Database Connection Management
class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            st.error("❌ DATABASE_URL environment variable not found")
            st.info("💡 Add DATABASE_URL to your Hugging Face Space environment variables.")
            st.stop()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with automatic cleanup"""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            st.error("❌ Database connection failed. Please try refreshing the page.")
            raise
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            st.error(f"❌ Database error: {e}")
            raise
        finally:
            if conn and not conn.closed:
                conn.close()
    
    def execute_query(self, query, params=None, fetch_type='all'):
        """Execute query with proper connection management and error handling"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                with self.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    
                    if fetch_type == 'all':
                        columns = [desc[0] for desc in cursor.description] if cursor.description else []
                        data = cursor.fetchall()
                        cursor.close()
                        
                        if data and columns:
                            return pd.DataFrame(data, columns=columns)
                        else:
                            return pd.DataFrame()
                    
                    elif fetch_type == 'one':
                        result = cursor.fetchone()
                        cursor.close()
                        return result
                    
                    else:  # For INSERT/UPDATE/DELETE
                        conn.commit()
                        cursor.close()
                        return True
                        
            except psycopg2.InterfaceError as e:
                logger.warning(f"Connection interface error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    st.error("❌ Database connection failed after multiple retries")
                    return pd.DataFrame() if fetch_type == 'all' else None
                    
            except psycopg2.OperationalError as e:
                logger.warning(f"Database operational error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    st.error("❌ Database server error. Please try again later.")
                    return pd.DataFrame() if fetch_type == 'all' else None
                    
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                st.error(f"❌ Query execution failed: {e}")
                return pd.DataFrame() if fetch_type == 'all' else None

# Create global database manager instance
@st.cache_resource
def get_database_manager():
    """Get database manager instance (cached)"""
    return DatabaseManager()

# Optimized query functions with caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def run_query(query, params=None):
    """Run query with proper error handling and caching"""
    try:
        db_manager = get_database_manager()
        return db_manager.execute_query(query, params, fetch_type='all')
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return pd.DataFrame()

def execute_query(query, params=None):
    """Execute INSERT/UPDATE/DELETE queries"""
    try:
        db_manager = get_database_manager()
        # Clear cache after data modifications
        if any(keyword in query.upper() for keyword in ['INSERT', 'UPDATE', 'DELETE']):
            st.cache_data.clear()
        return db_manager.execute_query(query, params, fetch_type='execute')
    except Exception as e:
        logger.error(f"Execute failed: {e}")
        return False

# FIXED: Utility function with proper type conversion
def get_next_id(table, id_column):
    """Get next available ID for a table - FIXED numpy.int64 issue"""
    try:
        result = run_query(f"SELECT COALESCE(MAX({id_column}), 0) + 1 as next_id FROM {table}")
        if not result.empty and 'next_id' in result.columns:
            # Convert numpy.int64 to regular Python int to fix psycopg2 adaptation error
            next_id = int(result['next_id'].iloc[0])
            return next_id
        else:
            return 1
    except Exception as e:
        logger.error(f"Error getting next ID for {table}: {e}")
        return 1

# Updated main application with better connection testing
def main():
    # Header with connection status
    st.markdown('<h1 class="main-header">🍽️ Food Wastage Management System</h1>', unsafe_allow_html=True)
    st.markdown("**Connecting Food Donors with Those in Need | Powered by Neon PostgreSQL**")
    
    # Test database connection at startup
    try:
        db_manager = get_database_manager()
        test_result = db_manager.execute_query("SELECT 1 as test", fetch_type='one')
        if test_result:
            st.success("✅ Database connection established")
        else:
            st.error("❌ Database connection test failed")
            st.info("💡 Please check your DATABASE_URL environment variable in Hugging Face Space settings")
            return
    except Exception as e:
        st.error(f"❌ Database connection error: {e}")
        st.info("💡 Please check your DATABASE_URL environment variable in Hugging Face Space settings")
        return
    
    # Sidebar navigation
    st.sidebar.title("📋 Navigation")
    st.sidebar.markdown("---")
    
    page = st.sidebar.selectbox(
        "Choose a section:",
        [
            "📊 Dashboard", 
            "🍽️ Available Food", 
            "➕ Add Food Item", 
            "🏢 Providers", 
            "🏠 Receivers", 
            "📋 Claims Management", 
            "📈 Analytics",
            "🔍 Data Quality"
        ]
    )
    
    # Page routing
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "🍽️ Available Food":
        show_available_food()
    elif page == "➕ Add Food Item":
        add_food_item()
    elif page == "🏢 Providers":
        show_providers()
    elif page == "🏠 Receivers":
        show_receivers()
    elif page == "📋 Claims Management":
        show_claims_management()
    elif page == "📈 Analytics":
        show_analytics()
    elif page == "🔍 Data Quality":
        show_data_quality()

@st.cache_data(ttl=300)
def get_dashboard_metrics():
    """Cached dashboard metrics"""
    metrics = {}
    try:
        total_items_df = run_query("SELECT COUNT(*) as count FROM food_items")
        metrics['total_items'] = total_items_df['count'].iloc[0] if not total_items_df.empty else 0
        
        available_items_df = run_query("SELECT COUNT(*) as count FROM food_items WHERE status = 'Available'")
        metrics['available_items'] = available_items_df['count'].iloc[0] if not available_items_df.empty else 0
        
        active_providers_df = run_query("SELECT COUNT(DISTINCT provider_id) as count FROM food_items")
        metrics['active_providers'] = active_providers_df['count'].iloc[0] if not active_providers_df.empty else 0
        
        total_claims_df = run_query("SELECT COUNT(*) as count FROM claims")
        metrics['total_claims'] = total_claims_df['count'].iloc[0] if not total_claims_df.empty else 0
        
        completed_claims_df = run_query("SELECT COUNT(*) as count FROM claims WHERE status = 'Completed'")
        metrics['completed_claims'] = completed_claims_df['count'].iloc[0] if not completed_claims_df.empty else 0
        
        active_cities_df = run_query("SELECT COUNT(DISTINCT city) as count FROM providers")
        metrics['active_cities'] = active_cities_df['count'].iloc[0] if not active_cities_df.empty else 0
        
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
    
    return metrics

def show_dashboard():
    """Dashboard with improved error handling and caching"""
    st.header("📊 System Overview Dashboard")
    
    try:
        # Get cached metrics
        metrics = get_dashboard_metrics()
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Food Items", f"{metrics.get('total_items', 0):,}", delta="All time")
        
        with col2:
            st.metric("Available Items", f"{metrics.get('available_items', 0):,}", delta="Ready to claim")
        
        with col3:
            st.metric("Active Providers", f"{metrics.get('active_providers', 0):,}", delta="Food donors")
        
        with col4:
            st.metric("Total Claims", f"{metrics.get('total_claims', 0):,}", delta="All time")
        
        # Charts with error handling
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🥘 Food Types Distribution")
            try:
                food_types = run_query("""
                    SELECT food_type, COUNT(*) as count 
                    FROM food_items 
                    WHERE status = 'Available'
                    GROUP BY food_type
                    ORDER BY count DESC
                """)
                if not food_types.empty:
                    fig = px.pie(food_types, values='count', names='food_type',
                                color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#45B7D1'])
                    fig.update_traces(textposition='inside', textinfo='percent+label+value')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No food type data available")
            except Exception as e:
                st.error("Error loading food types chart")
                logger.error(f"Food types chart error: {e}")
        
        with col2:
            st.subheader("🍽️ Meal Types Available")
            try:
                meal_types = run_query("""
                    SELECT meal_type, COUNT(*) as count 
                    FROM food_items 
                    WHERE status = 'Available'
                    GROUP BY meal_type
                    ORDER BY count DESC
                """)
                if not meal_types.empty:
                    fig = px.bar(meal_types, x='meal_type', y='count',
                                color='meal_type', 
                                color_discrete_sequence=['#FF9F43', '#10AC84', '#EE5A24', '#5F27CD'])
                    fig.update_layout(showlegend=False, xaxis_title="Meal Type", yaxis_title="Number of Items")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No meal type data available")
            except Exception as e:
                st.error("Error loading meal types chart")
                logger.error(f"Meal types chart error: {e}")
        
        # Recent activities
        st.subheader("🆕 Recently Added Food Items")
        try:
            recent_items = run_query("""
                SELECT fi.food_name, fi.quantity, fi.food_type, fi.meal_type, 
                       fi.expiry_date, p.name as provider_name, fi.location,
                       fi.posted_date
                FROM food_items fi
                JOIN providers p ON fi.provider_id = p.provider_id
                WHERE fi.status = 'Available'
                ORDER BY fi.posted_date DESC
                LIMIT 10
            """)
            
            if not recent_items.empty:
                st.dataframe(recent_items, use_container_width=True)
            else:
                st.info("No recent food items found")
        except Exception as e:
            st.error("Error loading recent items")
            logger.error(f"Recent items error: {e}")
        
        # System health indicators
        st.subheader("🔋 System Health")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_claims = metrics.get('total_claims', 0)
            completed_claims = metrics.get('completed_claims', 0)
            success_rate = (completed_claims / total_claims * 100) if total_claims > 0 else 0
            st.metric("Claims Success Rate", f"{success_rate:.1f}%")
        
        with col2:
            total_items = metrics.get('total_items', 0)
            available_items = metrics.get('available_items', 0)
            availability_rate = (available_items / total_items * 100) if total_items > 0 else 0
            st.metric("Food Availability", f"{availability_rate:.1f}%")
        
        with col3:
            st.metric("Active Cities", f"{metrics.get('active_cities', 0)}")
                
    except Exception as e:
        st.error(f"❌ Dashboard loading failed: {e}")
        logger.error(f"Dashboard error: {e}")

@st.cache_data(ttl=300)
def get_available_food_filters():
    """Cached filter options for available food"""
    filters = {}
    try:
        food_types = run_query("SELECT DISTINCT food_type FROM food_items WHERE status = 'Available' ORDER BY food_type")
        filters['food_types'] = ["All"] + food_types['food_type'].tolist() if not food_types.empty else ["All"]
        
        meal_types = run_query("SELECT DISTINCT meal_type FROM food_items WHERE status = 'Available' ORDER BY meal_type")
        filters['meal_types'] = ["All"] + meal_types['meal_type'].tolist() if not meal_types.empty else ["All"]
        
        locations = run_query("SELECT DISTINCT location FROM food_items WHERE status = 'Available' ORDER BY location")
        filters['locations'] = ["All"] + locations['location'].tolist() if not locations.empty else ["All"]
    except Exception as e:
        logger.error(f"Error getting filters: {e}")
        filters = {'food_types': ['All'], 'meal_types': ['All'], 'locations': ['All']}
    
    return filters

def show_available_food():
    """Browse and search available food items with improved error handling"""
    st.header("🍽️ Available Food Items")
    
    # Get cached filters
    filters = get_available_food_filters()
    
    # Filters with error handling
    col1, col2, col3 = st.columns(3)
    
    with col1:
        food_type_filter = st.selectbox("Food Type", filters['food_types'])
    
    with col2:
        meal_type_filter = st.selectbox("Meal Type", filters['meal_types'])
    
    with col3:
        location_filter = st.selectbox("Location", filters['locations'])
    
    # Search functionality
    search_term = st.text_input("🔍 Search food items", placeholder="Enter food name or keyword...")
    
    # Build dynamic query
    query = """
        SELECT fi.food_id, fi.food_name, fi.quantity, fi.expiry_date, 
               fi.location, fi.food_type, fi.meal_type, fi.posted_date,
               p.name as provider_name, p.contact as provider_contact,
               p.city as provider_city
        FROM food_items fi
        JOIN providers p ON fi.provider_id = p.provider_id
        WHERE fi.status = 'Available'
    """
    params = []
    
    if food_type_filter != "All":
        query += " AND fi.food_type = %s"
        params.append(food_type_filter)
    
    if meal_type_filter != "All":
        query += " AND fi.meal_type = %s"
        params.append(meal_type_filter)
    
    if location_filter != "All":
        query += " AND fi.location = %s"
        params.append(location_filter)
    
    if search_term:
        query += " AND (fi.food_name ILIKE %s OR fi.location ILIKE %s)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])
    
    query += " ORDER BY fi.expiry_date ASC"
    
    # Execute query and display results
    try:
        available_food = run_query(query, params if params else None)
        
        if not available_food.empty:
            st.success(f"Found {len(available_food)} available food items")
            
            # Display as cards or table
            display_mode = st.radio("Display Mode", ["Table", "Cards"], horizontal=True)
            
            if display_mode == "Table":
                st.dataframe(available_food, use_container_width=True)
            else:
                # Card view
                for idx, row in available_food.iterrows():
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.write(f"**{row['food_name']}**")
                            st.write(f"📍 {row['location']} | 🏢 {row['provider_name']}")
                            st.write(f"📞 {row['provider_contact']}")
                        with col2:
                            st.write(f"🥗 {row['food_type']}")
                            st.write(f"🍽️ {row['meal_type']}")
                            st.write(f"📅 Expires: {row['expiry_date']}")
                        with col3:
                            st.write(f"**Qty: {row['quantity']}**")
                            if st.button(f"Claim", key=f"claim_{row['food_id']}"):
                                st.session_state[f'claim_food_id'] = row['food_id']
                                st.rerun()
                        st.markdown("---")
        else:
            st.info("No food items match your criteria")
    except Exception as e:
        st.error(f"Error loading available food items: {e}")
        logger.error(f"Available food query error: {e}")
    
    # Handle food claiming
    if 'claim_food_id' in st.session_state:
        claim_food_item(st.session_state['claim_food_id'])

def claim_food_item(food_id):
    """Handle food item claiming with improved error handling"""
    st.subheader("📋 Claim Food Item")
    
    try:
        # Get food item details
        food_details = run_query("SELECT * FROM food_items WHERE food_id = %s", [food_id])
        
        if not food_details.empty:
            food = food_details.iloc[0]
            st.write(f"**Food Item:** {food['food_name']}")
            st.write(f"**Quantity:** {food['quantity']}")
            st.write(f"**Location:** {food['location']}")
            
            with st.form("claim_form"):
                # Get receivers for dropdown
                receivers = run_query("SELECT receiver_id, name FROM receivers ORDER BY name")
                if not receivers.empty:
                    receiver_options = {f"{row['name']} (ID: {row['receiver_id']})": int(row['receiver_id']) 
                                      for _, row in receivers.iterrows()}
                    selected_receiver = st.selectbox("Select Receiver", list(receiver_options.keys()))
                else:
                    st.error("No receivers found in the system")
                    return
                
                notes = st.text_area("Additional Notes (Optional)")
                
                submitted = st.form_submit_button("Submit Claim")
                
                if submitted:
                    # Insert claim record
                    claim_id = get_next_id('claims', 'claim_id')
                    claim_query = """
                        INSERT INTO claims (claim_id, food_id, receiver_id, status, claim_timestamp, notes)
                        VALUES (%s, %s, %s, 'Pending', %s, %s)
                    """
                    
                    if execute_query(claim_query, [
                        claim_id, int(food_id), receiver_options[selected_receiver], 
                        datetime.now(), notes
                    ]):
                        # Update food item status
                        update_query = "UPDATE food_items SET status = 'Claimed' WHERE food_id = %s"
                        execute_query(update_query, [int(food_id)])
                        
                        st.success("✅ Claim submitted successfully!")
                        st.balloons()
                        
                        # Clear session state
                        del st.session_state['claim_food_id']
                        st.rerun()
        else:
            st.error("Food item not found")
    except Exception as e:
        st.error(f"Error processing claim: {e}")
        logger.error(f"Claim processing error: {e}")

@st.cache_data(ttl=300)
def get_providers_for_dropdown():
    """Cached providers for dropdown"""
    try:
        providers = run_query("SELECT provider_id, name FROM providers ORDER BY name")
        if not providers.empty:
            return {f"{row['name']} (ID: {row['provider_id']})": int(row['provider_id']) 
                   for _, row in providers.iterrows()}
        else:
            return {}
    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return {}

def add_food_item():
    """Add new food item with FIXED numpy.int64 error"""
    st.header("➕ Add New Food Item")
    
    try:
        # Get cached providers
        provider_options = get_providers_for_dropdown()
        
        if not provider_options:
            st.error("No providers found. Please add providers first.")
            return
        
        with st.form("add_food_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                selected_provider = st.selectbox("Select Provider*", list(provider_options.keys()))
                food_name = st.text_input("Food Name*", placeholder="e.g., Vegetable Curry")
                quantity = st.number_input("Quantity*", min_value=1, value=1)
                expiry_date = st.date_input("Expiry Date*", 
                                           value=datetime.now().date() + timedelta(days=3),
                                           min_value=datetime.now().date())
            
            with col2:
                location = st.text_input("Location*", placeholder="e.g., Downtown Restaurant")
                food_type = st.selectbox("Food Type*", ["Vegetarian", "Non-Vegetarian", "Vegan"])
                meal_type = st.selectbox("Meal Type*", ["Breakfast", "Lunch", "Dinner", "Snacks"])
            
            submitted = st.form_submit_button("🍽️ Add Food Item", use_container_width=True)
            
            if submitted:
                if food_name and location:
                    try:
                        food_id = get_next_id('food_items', 'food_id')
                        
                        insert_query = """
                            INSERT INTO food_items (food_id, food_name, quantity, expiry_date, 
                                                  provider_id, location, food_type, meal_type)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        
                        # FIXED: Ensure all IDs are converted to regular Python int
                        if execute_query(insert_query, [
                            int(food_id), 
                            food_name, 
                            int(quantity), 
                            expiry_date,
                            int(provider_options[selected_provider]), 
                            location, 
                            food_type, 
                            meal_type
                        ]):
                            st.success(f"✅ Food item '{food_name}' added successfully!")
                            st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Error adding food item: {e}")
                        logger.error(f"Add food item error: {e}")
                else:
                    st.error("❌ Please fill in all required fields marked with *")
    except Exception as e:
        st.error(f"Error loading add food form: {e}")
        logger.error(f"Add food form error: {e}")

@st.cache_data(ttl=300)
def get_providers_list():
    """Cached providers list"""
    try:
        return run_query("""
            SELECT p.*, COUNT(fi.food_id) as items_posted
            FROM providers p
            LEFT JOIN food_items fi ON p.provider_id = fi.provider_id
            GROUP BY p.provider_id, p.name, p.provider_type, p.address, p.city, p.contact
            ORDER BY items_posted DESC
        """)
    except Exception as e:
        logger.error(f"Error getting providers list: {e}")
        return pd.DataFrame()

def show_providers():
    """Manage providers with FIXED numpy.int64 error"""
    st.header("🏢 Provider Management")
    
    tab1, tab2 = st.tabs(["View Providers", "Add New Provider"])
    
    with tab1:
        try:
            providers = get_providers_list()
            if not providers.empty:
                st.dataframe(providers, use_container_width=True)
            else:
                st.info("No providers found")
        except Exception as e:
            st.error(f"Error loading providers: {e}")
            logger.error(f"Providers view error: {e}")
    
    with tab2:
        try:
            with st.form("add_provider_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    provider_name = st.text_input("Provider Name*")
                    provider_type = st.selectbox("Provider Type*", 
                                               ["Restaurant", "Grocery Store", "Catering Service", "Supermarket"])
                    city = st.text_input("City*")
                
                with col2:
                    address = st.text_area("Address")
                    contact = st.text_input("Contact Number")
                
                submitted = st.form_submit_button("Add Provider")
                
                if submitted and provider_name and city:
                    try:
                        provider_id = get_next_id('providers', 'provider_id')
                        
                        insert_query = """
                            INSERT INTO providers (provider_id, name, provider_type, address, city, contact)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        
                        # FIXED: Convert to regular Python int
                        if execute_query(insert_query, [
                            int(provider_id), 
                            provider_name, 
                            provider_type, 
                            address, 
                            city, 
                            contact
                        ]):
                            st.success("✅ Provider added successfully!")
                            # Clear relevant caches
                            get_providers_list.clear()
                            get_providers_for_dropdown.clear()
                    except Exception as e:
                        st.error(f"❌ Error adding provider: {e}")
                        logger.error(f"Add provider error: {e}")
        except Exception as e:
            st.error(f"Error in add provider form: {e}")
            logger.error(f"Add provider error: {e}")

@st.cache_data(ttl=300)
def get_receivers_list():
    """Cached receivers list"""
    try:
        return run_query("""
            SELECT r.*, COUNT(c.claim_id) as total_claims
            FROM receivers r
            LEFT JOIN claims c ON r.receiver_id = c.receiver_id
            GROUP BY r.receiver_id, r.name, r.receiver_type, r.city, r.contact
            ORDER BY total_claims DESC
        """)
    except Exception as e:
        logger.error(f"Error getting receivers list: {e}")
        return pd.DataFrame()

def show_receivers():
    """Manage receivers with FIXED numpy.int64 error"""
    st.header("🏠 Receiver Management")
    
    tab1, tab2 = st.tabs(["View Receivers", "Add New Receiver"])
    
    with tab1:
        try:
            receivers = get_receivers_list()
            if not receivers.empty:
                st.dataframe(receivers, use_container_width=True)
            else:
                st.info("No receivers found")
        except Exception as e:
            st.error(f"Error loading receivers: {e}")
            logger.error(f"Receivers view error: {e}")
    
    with tab2:
        try:
            with st.form("add_receiver_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    receiver_name = st.text_input("Receiver Name*")
                    receiver_type = st.selectbox("Receiver Type*", 
                                               ["Individual", "NGO", "Shelter", "Charity"])
                
                with col2:
                    city = st.text_input("City*")
                    contact = st.text_input("Contact Number")
                
                submitted = st.form_submit_button("Add Receiver")
                
                if submitted and receiver_name and city:
                    try:
                        receiver_id = get_next_id('receivers', 'receiver_id')
                        
                        insert_query = """
                            INSERT INTO receivers (receiver_id, name, receiver_type, city, contact)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        
                        # FIXED: Convert to regular Python int
                        if execute_query(insert_query, [
                            int(receiver_id), 
                            receiver_name, 
                            receiver_type, 
                            city, 
                            contact
                        ]):
                            st.success("✅ Receiver added successfully!")
                            # Clear relevant caches
                            get_receivers_list.clear()
                    except Exception as e:
                        st.error(f"❌ Error adding receiver: {e}")
                        logger.error(f"Add receiver error: {e}")
        except Exception as e:
            st.error(f"Error in add receiver form: {e}")
            logger.error(f"Add receiver error: {e}")

@st.cache_data(ttl=300)
def get_claims_data():
    """Cached claims data"""
    try:
        summary = {}
        summary['total'] = run_query("SELECT COUNT(*) as count FROM claims")['count'].iloc[0]
        summary['pending'] = run_query("SELECT COUNT(*) as count FROM claims WHERE status = 'Pending'")['count'].iloc[0]
        summary['completed'] = run_query("SELECT COUNT(*) as count FROM claims WHERE status = 'Completed'")['count'].iloc[0]
        summary['cancelled'] = run_query("SELECT COUNT(*) as count FROM claims WHERE status = 'Cancelled'")['count'].iloc[0]
        
        recent_claims = run_query("""
            SELECT c.claim_id, c.status, c.claim_timestamp, c.pickup_status,
                   fi.food_name, fi.quantity, fi.food_type,
                   r.name as receiver_name, r.receiver_type,
                   p.name as provider_name, p.contact as provider_contact
            FROM claims c
            JOIN food_items fi ON c.food_id = fi.food_id
            JOIN receivers r ON c.receiver_id = r.receiver_id
            JOIN providers p ON fi.provider_id = p.provider_id
            ORDER BY c.claim_timestamp DESC
            LIMIT 20
        """)
        
        return summary, recent_claims
    except Exception as e:
        logger.error(f"Error getting claims data: {e}")
        return {}, pd.DataFrame()

def show_claims_management():
    """Claims management interface with improved error handling"""
    st.header("📋 Claims Management")
    
    try:
        # Get cached claims data
        summary, recent_claims = get_claims_data()
        
        # Claims summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Claims", f"{summary.get('total', 0):,}")
        
        with col2:
            st.metric("Pending Claims", f"{summary.get('pending', 0):,}")
        
        with col3:
            st.metric("Completed Claims", f"{summary.get('completed', 0):,}")
        
        with col4:
            st.metric("Cancelled Claims", f"{summary.get('cancelled', 0):,}")
        
        # Recent claims
        st.subheader("Recent Claims")
        
        if not recent_claims.empty:
            st.dataframe(recent_claims, use_container_width=True)
            
            # Update claim status
            st.subheader("Update Claim Status")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                claim_ids = recent_claims['claim_id'].tolist()
                selected_claim = st.selectbox("Select Claim ID", claim_ids)
            
            with col2:
                new_status = st.selectbox("New Status", ["Pending", "Completed", "Cancelled"])
            
            with col3:
                if st.button("Update Status"):
                    update_query = "UPDATE claims SET status = %s WHERE claim_id = %s"
                    if execute_query(update_query, [new_status, int(selected_claim)]):
                        st.success("✅ Claim status updated!")
                        get_claims_data.clear()
                        st.rerun()
        else:
            st.info("No claims found")
    except Exception as e:
        st.error(f"Error loading claims management: {e}")
        logger.error(f"Claims management error: {e}")

@st.cache_data(ttl=300)
def get_analytics_data():
    """Cached analytics data"""
    try:
        analytics = {}
        
        # Claims status distribution
        analytics['claims_status'] = run_query("""
            SELECT status, COUNT(*) as count
            FROM claims
            GROUP BY status
            ORDER BY count DESC
        """)
        
        # Top cities by providers
        analytics['provider_cities'] = run_query("""
            SELECT city, COUNT(*) as provider_count
            FROM providers
            GROUP BY city
            ORDER BY provider_count DESC
            LIMIT 10
        """)
        
        # Food distribution by provider type
        analytics['provider_performance'] = run_query("""
            SELECT p.provider_type, COUNT(fi.food_id) as items_posted
            FROM providers p
            JOIN food_items fi ON p.provider_id = fi.provider_id
            GROUP BY p.provider_type
            ORDER BY items_posted DESC
        """)
        
        # System metrics
        total_items = run_query("SELECT COUNT(*) as count FROM food_items")['count'].iloc[0]
        available_items = run_query("SELECT COUNT(*) as count FROM food_items WHERE status = 'Available'")['count'].iloc[0]
        total_providers = run_query("SELECT COUNT(*) as count FROM providers")['count'].iloc[0]
        total_claims = run_query("SELECT COUNT(*) as count FROM claims")['count'].iloc[0]
        completed = run_query("SELECT COUNT(*) as count FROM claims WHERE status = 'Completed'")['count'].iloc[0]
        
        analytics['metrics'] = {
            'total_items': total_items,
            'available_items': available_items,
            'total_providers': total_providers,
            'total_claims': total_claims,
            'completed': completed
        }
        
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics data: {e}")
        return {}

def show_analytics():
    """Analytics and insights dashboard - REMOVED temporal analysis as requested"""
    st.header("📈 Analytics & Insights")
    
    try:
        # Get cached analytics data
        analytics = get_analytics_data()
        
        # Claims status distribution and Geographic analysis
        st.subheader("📊 Claims & Geographic Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Claims status distribution
            claims_status = analytics.get('claims_status', pd.DataFrame())
            if not claims_status.empty:
                fig = px.bar(claims_status, x='status', y='count',
                            title="Claims Status Distribution",
                            color='status')
                fig.update_layout(showlegend=False, xaxis_title="Claim Status", yaxis_title="Number of Claims")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No claims data available")
        
        with col2:
            # Top cities by providers
            provider_cities = analytics.get('provider_cities', pd.DataFrame())
            if not provider_cities.empty:
                fig = px.bar(provider_cities, x='city', y='provider_count',
                            title="Top 10 Cities by Provider Count")
                fig.update_layout(xaxis_title="City", yaxis_title="Number of Providers")
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No provider city data available")
        
        # Provider performance
        st.subheader("🏢 Provider Performance")
        
        provider_performance = analytics.get('provider_performance', pd.DataFrame())
        if not provider_performance.empty:
            fig = px.pie(provider_performance, values='items_posted', names='provider_type',
                        title="Food Items by Provider Type")
            fig.update_traces(textposition='inside', textinfo='percent+label+value')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No provider performance data available")
        
        # Key insights
        st.subheader("💡 Key Insights")
        
        metrics = analytics.get('metrics', {})
        
        insights = []
        total_items = metrics.get('total_items', 0)
        available_items = metrics.get('available_items', 0)
        total_providers = metrics.get('total_providers', 0)
        total_claims = metrics.get('total_claims', 0)
        completed = metrics.get('completed', 0)
        
        insights.append(f"📊 **System Scale**: {total_items:,} food items from {total_providers:,} providers")
        if total_items > 0:
            insights.append(f"🍽️ **Current Availability**: {available_items:,} items available ({available_items/total_items*100:.1f}%)")
        
        if total_claims > 0:
            success_rate = completed / total_claims * 100
            insights.append(f"✅ **Claims Success Rate**: {success_rate:.1f}% ({completed:,} completed out of {total_claims:,})")
        
        # Display insights
        for insight in insights:
            st.markdown(f"- {insight}")
            
    except Exception as e:
        st.error(f"Error loading analytics: {e}")
        logger.error(f"Analytics error: {e}")

def show_data_quality():
    """Data quality monitoring - FIXED column name errors"""
    st.header("🔍 Data Quality Monitor")
    
    try:
        # FIXED: Table completeness metrics with correct column names
        tables_info = [
            ('providers', 'provider_id'),
            ('receivers', 'receiver_id'),
            ('food_items', 'food_id'),
            ('claims', 'claim_id')
        ]
        
        quality_data = []
        
        for table_name, id_column in tables_info:
            try:
                # FIXED: Use correct column names
                table_info = run_query(f"""
                    SELECT 
                        '{table_name}' as table_name,
                        COUNT(*) as total_records,
                        COUNT(CASE WHEN {id_column} IS NOT NULL THEN 1 END) as valid_ids
                    FROM {table_name}
                """)
                
                if not table_info.empty:
                    record = table_info.iloc[0]
                    quality_data.append({
                        'Table': record['table_name'],
                        'Total Records': record['total_records'],
                        'Valid IDs': record['valid_ids'],
                        'Quality Score': 'Good' if record['total_records'] == record['valid_ids'] else 'Issues'
                    })
            except Exception as e:
                quality_data.append({
                    'Table': table_name,
                    'Total Records': 0,
                    'Valid IDs': 0,
                    'Quality Score': 'Error'
                })
                logger.error(f"Table {table_name} quality check error: {e}")
        
        # Display quality metrics
        if quality_data:
            quality_df = pd.DataFrame(quality_data)
            st.dataframe(quality_df, use_container_width=True)
        
        # Data integrity checks
        st.subheader("🔒 Data Integrity Checks")
        
        integrity_checks = {
            "Orphaned Food Items": "SELECT COUNT(*) as count FROM food_items fi LEFT JOIN providers p ON fi.provider_id = p.provider_id WHERE p.provider_id IS NULL",
            "Orphaned Claims": "SELECT COUNT(*) as count FROM claims c LEFT JOIN food_items fi ON c.food_id = fi.food_id WHERE fi.food_id IS NULL",
            "Invalid Quantities": "SELECT COUNT(*) as count FROM food_items WHERE quantity <= 0",
            "Future Posting Dates": "SELECT COUNT(*) as count FROM food_items WHERE posted_date > CURRENT_TIMESTAMP"
        }
        
        for check_name, query in integrity_checks.items():
            try:
                result = run_query(query)
                if not result.empty:
                    count = result['count'].iloc[0]
                    status = "✅ OK" if count == 0 else f"⚠️ {count} issues"
                    st.write(f"**{check_name}**: {status}")
            except Exception as e:
                st.write(f"**{check_name}**: ❌ Check failed")
                logger.error(f"Integrity check {check_name} error: {e}")
        
        # Database statistics
        st.subheader("📊 Database Statistics")
        
        try:
            db_stats = run_query("""
                SELECT 
                    'Providers' as entity, COUNT(*) as count FROM providers
                UNION ALL
                SELECT 'Receivers', COUNT(*) FROM receivers
                UNION ALL
                SELECT 'Food Items', COUNT(*) FROM food_items
                UNION ALL
                SELECT 'Claims', COUNT(*) FROM claims
            """)
            
            if not db_stats.empty:
                fig = px.bar(db_stats, x='entity', y='count',
                            title="Database Entity Counts")
                fig.update_layout(xaxis_title="Entity Type", yaxis_title="Record Count")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error generating database statistics: {e}")
            logger.error(f"Database statistics error: {e}")
            
    except Exception as e:
        st.error(f"Error loading data quality monitor: {e}")
        logger.error(f"Data quality monitor error: {e}")

# Footer
def show_footer():
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        🍽️ <b>Food Wastage Management System</b> | 
        Reducing food waste, one meal at a time | 
        Powered by <b>Neon PostgreSQL</b> & <b>Streamlit</b> | 
        Deployed on <b>Hugging Face Spaces</b>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    show_footer()
