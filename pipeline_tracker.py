
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

class PipelineTracker:
    """Persistent pipeline tracker for job applications using Markdown"""
    
    def __init__(self, tracker_path: str = "data/applications.md"):
        self.tracker_path = tracker_path
        self._ensure_tracker_exists()
    
    def _ensure_tracker_exists(self):
        """Create tracker file if it doesn't exist"""
        path = Path(self.tracker_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if not path.exists():
            self._create_empty_tracker()
    
    def _create_empty_tracker(self):
        """Create empty tracker with header"""
        content = """# Job Applications Tracker

| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|

## Status Reference
- **Evaluated**: Job has been reviewed and scored
- **Applied**: Application submitted
- **Interview**: Interview scheduled or in progress
- **Offer**: Job offer received
- **Rejected**: Application rejected or not a good fit
- **Discarded**: Job no longer interested
- **SKIP**: Skip this job for now
"""
        with open(self.tracker_path, 'w') as f:
            f.write(content)
    
    def read_applications(self) -> pd.DataFrame:
        """Read applications from markdown tracker into DataFrame"""
        try:
            with open(self.tracker_path, 'r') as f:
                lines = f.readlines()
            
            # Find the table
            data_lines = []
            in_table = False
            
            for line in lines:
                if line.strip().startswith('|') and not in_table:
                    in_table = True
                    continue  # Skip header
                if line.strip().startswith('|') and in_table:
                    if line.strip() == '|---|------|---------|------|-------|--------|-----|--------|-------|':
                        continue  # Skip separator
                    data_lines.append(line.strip())
                elif in_table and not line.strip().startswith('|'):
                    break
            
            # Parse table data
            jobs = []
            for line in data_lines:
                if not line:
                    continue
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) >= 8:
                    jobs.append({
                        'Index': cells[0],
                        'Date': cells[1],
                        'Company': cells[2],
                        'Role': cells[3],
                        'Score': cells[4],
                        'Status': cells[5],
                        'PDF': cells[6],
                        'Report': cells[7],
                        'Notes': cells[8] if len(cells) > 8 else ''
                    })
            
            return pd.DataFrame(jobs) if jobs else pd.DataFrame()
        
        except Exception as e:
            print(f"⚠️ Error reading applications: {e}")
            return pd.DataFrame()
    
    def add_application(self, company: str, role: str, score: str, status: str, 
                       url: str = "", notes: str = "") -> bool:
        """Add a new application to the tracker"""
        try:
            with open(self.tracker_path, 'r') as f:
                content = f.read()
            
            # Find the next index
            lines = content.split('\n')
            max_index = 0
            for line in lines:
                if line.strip().startswith('|') and line.count('|') >= 9:
                    try:
                        idx = int(line.split('|')[1].strip())
                        max_index = max(max_index, idx)
                    except:
                        pass
            
            next_index = max_index + 1
            date = datetime.now().strftime('%Y-%m-%d')
            
            # Format new row
            new_row = f"| {next_index:03d} | {date} | {company} | {role} | {score} | {status} | ❌ | [Report](reports/{next_index:03d}-{self._slugify(company)}-{date}.md) | {notes} |"
            
            # Insert before the ## Status Reference section
            insert_pos = content.find('## Status Reference')
            if insert_pos != -1:
                content = content[:insert_pos] + new_row + '\n\n' + content[insert_pos:]
            else:
                content += '\n' + new_row
            
            with open(self.tracker_path, 'w') as f:
                f.write(content)
            
            print(f"✅ Added: {company} - {role}")
            return True
        
        except Exception as e:
            print(f"❌ Error adding application: {e}")
            return False
    
    def update_status(self, company: str, new_status: str) -> bool:
        """Update application status"""
        try:
            with open(self.tracker_path, 'r') as f:
                content = f.read()
            
            # Find and replace the status
            lines = content.split('\n')
            updated = False
            
            for i, line in enumerate(lines):
                if company in line and line.strip().startswith('|'):
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]
                    if len(cells) >= 6:
                        cells[5] = new_status  # Status column
                        new_line = '| ' + ' | '.join(cells) + ' |'
                        lines[i] = new_line
                        updated = True
                        break
            
            if updated:
                with open(self.tracker_path, 'w') as f:
                    f.write('\n'.join(lines))
                print(f"✅ Updated {company} status to {new_status}")
                return True
            else:
                print(f"⚠️ Company not found: {company}")
                return False
        
        except Exception as e:
            print(f"❌ Error updating status: {e}")
            return False
    
    def get_statistics(self) -> dict:
        """Get pipeline statistics"""
        df = self.read_applications()
        
        if df.empty:
            return {
                'total': 0,
                'by_status': {},
                'avg_score': 0,
                'highest_score': 0,
                'lowest_score': 0
            }
        
        stats = {
            'total': len(df),
            'by_status': df['Status'].value_counts().to_dict(),
            'avg_score': self._extract_numeric_scores(df['Score']).mean(),
            'highest_score': self._extract_numeric_scores(df['Score']).max(),
            'lowest_score': self._extract_numeric_scores(df['Score']).min(),
        }
        
        return stats
    
    @staticmethod
    def _extract_numeric_scores(scores) -> pd.Series:
        """Extract numeric part from scores like '4.5/5'"""
        return scores.str.split('/').str[0].astype(float, errors='ignore')
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to slug format"""
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')


if __name__ == "__main__":
    tracker = PipelineTracker()
    
    # Example usage
    tracker.add_application(
        company="Google",
        role="ML Engineer",
        score="4.5/5",
        status="Applied",
        notes="Strong culture fit"
    )
    
    print("\n📊 Statistics:")
    stats = tracker.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
