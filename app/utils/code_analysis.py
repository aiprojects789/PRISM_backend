# app/utils/code_analysis.py - Analyze and identify unused files

import os
import ast
import re
from typing import Set, Dict, List
from pathlib import Path

class CodeAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.python_files = []
        self.imports = {}
        self.unused_files = set()
        self.used_files = set()
        
    def scan_python_files(self):
        """Scan all Python files in the project"""
        for root, dirs, files in os.walk(self.project_root):
            # Skip common directories that don't contain source code
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'venv', 'env']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    self.python_files.append(file_path)
    
    def analyze_imports(self):
        """Analyze imports in all Python files"""
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the AST
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                self.imports[file_path] = imports
                
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
    
    def _extract_imports(self, tree) -> Set[str]:
        """Extract import statements from AST"""
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")
        
        return imports
    
    def find_unused_files(self) -> Dict[str, List[str]]:
        """Identify potentially unused files"""
        analysis_result = {
            "definitely_unused": [],
            "potentially_unused": [],
            "critical_files": [],
            "recommendations": []
        }
        
        # Files that are definitely used (entry points, main files, etc.)
        critical_patterns = [
            "main.py",
            "__init__.py", 
            "config.py",
            "settings.py"
        ]
        
        # Build dependency graph
        file_usage = {}
        
        for file_path in self.python_files:
            file_name = file_path.name
            relative_path = str(file_path.relative_to(self.project_root))
            
            # Check if it's a critical file
            if any(pattern in file_name.lower() for pattern in critical_patterns):
                analysis_result["critical_files"].append(relative_path)
                continue
            
            # Check if this file is imported by others
            is_imported = False
            module_name = self._get_module_name(file_path)
            
            for other_file, imports in self.imports.items():
                if other_file == file_path:
                    continue
                
                # Check various import patterns
                if any(imp for imp in imports if module_name in imp):
                    is_imported = True
                    break
            
            if not is_imported:
                analysis_result["potentially_unused"].append(relative_path)
        
        return analysis_result
    
    def _get_module_name(self, file_path: Path) -> str:
        """Get module name from file path"""
        relative_path = file_path.relative_to(self.project_root)
        module_parts = list(relative_path.parts[:-1])  # Remove filename
        module_parts.append(relative_path.stem)  # Add filename without extension
        return ".".join(module_parts)

# Specific analysis for your FastAPI project
def analyze_fastapi_project():
    """Analyze the specific FastAPI project structure"""
    
    # Based on the provided files, here's the analysis:
    
    files_analysis = {
        "USED_FILES": [
            "main.py",  # Entry point - CRITICAL
            "app/core/config.py",  # Configuration - CRITICAL  
            "app/core/firebase.py",  # Database connection - CRITICAL
            "app/core/security.py",  # Authentication - CRITICAL
            "app/core/utils.py",  # Utility functions - USED
            
            # Models (all used)
            "app/models/common.py",  # Base models - USED
            "app/models/conversation.py",  # Conversation models - USED  
            "app/models/interview.py",  # Interview models - USED
            "app/models/profile.py",  # Profile models - USED
            "app/models/user.py",  # User models - USED
            
            # Routers (all used and registered in main.py)
            "app/routers/auth.py",  # Authentication endpoints - USED
            "app/routers/conversations.py",  # Conversation endpoints - USED
            "app/routers/interview.py",  # Interview endpoints - USED
            "app/routers/profiles.py",  # Profile endpoints - USED
            "app/routers/questions.py",  # Question generation - USED
            "app/routers/recommendations.py",  # Recommendation endpoints - USED
        ],
        
        "POTENTIALLY_UNUSED": [
            "app/core/interview_agent.py",  # POTENTIALLY UNUSED - Logic moved to interview.py
            "app/core/profile_generator.py",  # POTENTIALLY UNUSED - Similar logic in questions.py
            "app/core/recommendation_engine.py",  # POTENTIALLY UNUSED - Logic in recommendations.py
        ],
        
        "ANALYSIS_NOTES": [
            "interview_agent.py: The TieredInterviewAgent class is defined here but the same logic is also in interview.py router. This creates duplication.",
            "profile_generator.py: ProfileGenerator class has similar functionality to what's in questions.py router.",
            "recommendation_engine.py: RecommendationEngine class duplicates logic in recommendations.py router.",
        ],
        
        "RECOMMENDATIONS": [
            "1. CONSOLIDATE: Move TieredInterviewAgent from interview_agent.py into interview.py and remove the separate file",
            "2. CONSOLIDATE: Move ProfileGenerator logic into questions.py and remove profile_generator.py", 
            "3. CONSOLIDATE: Move RecommendationEngine logic into recommendations.py and remove recommendation_engine.py",
            "4. REFACTOR: Create a shared 'services' directory for business logic that's used across multiple routers",
            "5. CLEAN UP: Remove any commented-out code from interview_agent.py (there's a large commented section)",
        ]
    }
    
    return files_analysis

def generate_cleanup_script():
    """Generate a cleanup script for the identified unused files"""
    
    cleanup_script = """#!/bin/bash
# Cleanup script for FastAPI project
# Run this after backing up your project

echo "Starting cleanup of unused files..."

# Create backup directory
mkdir -p backup/$(date +%Y%m%d_%H%M%S)

# Move potentially unused files to backup
echo "Moving potentially unused files to backup..."

# Backup files before removing
cp app/core/interview_agent.py backup/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "interview_agent.py not found"
cp app/core/profile_generator.py backup/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "profile_generator.py not found"  
cp app/core/recommendation_engine.py backup/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "recommendation_engine.py not found"

# Remove the files (uncomment after verification)
# rm app/core/interview_agent.py
# rm app/core/profile_generator.py  
# rm app/core/recommendation_engine.py

echo "Cleanup completed. Files backed up to backup/ directory"
echo "Uncomment the rm commands in this script to actually delete the files"
"""
    
    return cleanup_script

def create_services_directory_structure():
    """Suggest a better directory structure with services"""
    
    suggested_structure = """
Suggested refactored directory structure:

app/
├── core/
│   ├── __init__.py
│   ├── config.py          # ✓ Keep
│   ├── firebase.py        # ✓ Keep  
│   ├── security.py        # ✓ Keep
│   └── utils.py          # ✓ Keep
│
├── services/              # 🆕 NEW - Business logic layer
│   ├── __init__.py
│   ├── interview_service.py      # Move TieredInterviewAgent here
│   ├── profile_service.py        # Move ProfileGenerator here  
│   ├── recommendation_service.py # Move RecommendationEngine here
│   └── question_service.py       # Extract question generation logic
│
├── models/                # ✓ Keep all
│   ├── __init__.py
│   ├── common.py
│   ├── conversation.py
│   ├── interview.py
│   ├── profile.py
│   └── user.py
│
├── routers/               # ✓ Keep all, but simplify by using services
│   ├── __init__.py
│   ├── auth.py
│   ├── conversations.py
│   ├── interview.py       # Use interview_service
│   ├── profiles.py        # Use profile_service
│   ├── questions.py       # Use question_service
│   └── recommendations.py # Use recommendation_service
│
└── main.py               # ✓ Keep

Benefits of this structure:
1. Clear separation of concerns
2. Business logic is reusable across different routers
3. Easier to test individual services
4. Follows clean architecture principles
5. Eliminates code duplication
"""
    
    return suggested_structure

# Main analysis function
def main():
    print("=== FastAPI Project Analysis ===\n")
    
    # Analyze the project
    analysis = analyze_fastapi_project()
    
    print("📁 USED FILES:")
    for file in analysis["USED_FILES"]:
        print(f"  ✓ {file}")
    
    print("\n⚠️  POTENTIALLY UNUSED FILES:")
    for file in analysis["POTENTIALLY_UNUSED"]:
        print(f"  ⚠️  {file}")
    
    print("\n📝 ANALYSIS NOTES:")
    for note in analysis["ANALYSIS_NOTES"]:
        print(f"  • {note}")
    
    print("\n🔧 RECOMMENDATIONS:")
    for rec in analysis["RECOMMENDATIONS"]:
        print(f"  {rec}")
    
    print("\n" + "="*50)
    print("CLEANUP SCRIPT:")
    print("="*50)
    print(generate_cleanup_script())
    
    print("\n" + "="*50)
    print("SUGGESTED NEW STRUCTURE:")
    print("="*50)
    print(create_services_directory_structure())

if __name__ == "__main__":
    main()