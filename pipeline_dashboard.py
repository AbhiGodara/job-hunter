
import streamlit as st
import pandas as pd
from pipeline_tracker import PipelineTracker

class PipelineDashboard:
    """Interactive dashboard for job application pipeline"""
    
    def __init__(self):
        self.tracker = PipelineTracker()
    
    def render(self):
        """Main dashboard render function"""
        st.set_page_config(page_title="Job Pipeline Dashboard", layout="wide")
        
        st.header("📊 Job Pipeline Dashboard")
        
        # Get data
        df = self.tracker.read_applications()
        stats = self.tracker.get_statistics()
        
        if df.empty:
            st.info("📭 No applications tracked yet. Go to Job Search tab to find jobs!")
            return
        
        # Sidebar filters
        with st.sidebar:
            st.header("🔍 Filters")
            status_filter = st.multiselect(
                "Filter by Status",
                df['Status'].unique(),
                default=df['Status'].unique()
            )
            
            company_search = st.text_input("Search by Company", "")
            
            sort_by = st.selectbox(
                "Sort by",
                ["Date (Newest)", "Score (Highest)", "Company", "Status"]
            )
        
        # Apply filters
        filtered_df = df.copy()
        
        if status_filter:
            filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
        
        if company_search:
            filtered_df = filtered_df[filtered_df['Company'].str.contains(company_search, case=False, na=False)]
        
        # Sort
        if sort_by == "Date (Newest)":
            filtered_df = filtered_df.sort_values('Date', ascending=False)
        elif sort_by == "Score (Highest)":
            filtered_df['Score_numeric'] = filtered_df['Score'].str.extract('(\d+\.?\d*)')[0].astype(float)
            filtered_df = filtered_df.sort_values('Score_numeric', ascending=False)
        elif sort_by == "Company":
            filtered_df = filtered_df.sort_values('Company')
        
        # Statistics
        st.subheader("📈 Statistics")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Applications", stats.get('total', 0))
        with col2:
            avg_score = stats.get('avg_score', 0)
            st.metric("Average Score", f"{avg_score:.1f}" if avg_score else "N/A")
        with col3:
            st.metric("Highest Score", f"{stats.get('highest_score', 0):.1f}" if stats.get('highest_score') else "N/A")
        with col4:
            st.metric("Lowest Score", f"{stats.get('lowest_score', 0):.1f}" if stats.get('lowest_score') else "N/A")
        with col5:
            applied = len(df[df['Status'] == 'Applied'])
            st.metric("Applied", applied)
        
        # Status breakdown
        if stats.get('by_status'):
            st.subheader("📊 Status Breakdown")
            status_counts = pd.Series(stats['by_status'])
            st.bar_chart(status_counts)
        
        # Applications table
        st.subheader("📋 Applications")
        st.dataframe(
            filtered_df[['Date', 'Company', 'Role', 'Score', 'Status', 'Notes']],
            use_container_width=True,
            hide_index=True
        )
        
        # Actions
        st.subheader("🔧 Actions")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_company = st.selectbox("Select Company to Update", filtered_df['Company'].unique())
            if selected_company:
                new_status = st.selectbox(
                    "New Status",
                    ["Applied", "Interview", "Offer", "Rejected", "Discarded", "SKIP"]
                )
                if st.button("Update Status"):
                    if self.tracker.update_status(selected_company, new_status):
                        st.success(f"✅ Updated {selected_company} to {new_status}")
                        st.rerun()
        
        with col2:
            if st.button("🔄 Refresh Dashboard"):
                st.rerun()
        
        # Footer
        st.divider()
        st.caption(f"💾 Data stored in: data/applications.md | Last updated: {pd.Timestamp.now()}")


def main():
    dashboard = PipelineDashboard()
    dashboard.render()


if __name__ == "__main__":
    main()
