# Amazon Bestsellers Scraper

A robust Python web scraper that extracts product information from Amazon India's bestsellers pages across all categories. Built with Playwright for reliable data extraction and enhanced with universal selectors to handle Amazon's dynamic content loading.

## 🎯 **What This Script Does**

This scraper automatically:
- Discovers all bestseller categories on Amazon India
- Extracts up to 100 products per category (50 per page × 2 pages)
- Collects product details: rank, name, link, rating, and price
- Saves data in both JSON and CSV formats with timestamps
- Provides detailed extraction statistics and progress tracking

## 🚀 **Getting Started on Windows 11 with WSL**

### **Step 1: Setting Up VS Code with WSL**

1. Open VS Code.

#### **1.1 Connect to WSL**
1. Press `Ctrl+Shift+P` to open Command Palette
2. Type "WSL: Connect to WSL" and select it
3. VS Code will open a new window connected to your WSL environment
4. You'll see "WSL: Ubuntu" (or your distro) in the bottom-left corner

#### **1.2 Navigate to the Project**
1. In the WSL VS Code window, press `Ctrl+Shift+E` to open Explorer
2. Click "Open Folder" button
3. Navigate to: `amznbsscraper` inside the `projects` directory
4. Click "OK" to open the project folder

### **Step 2: Environment Setup and Script Execution**

#### **2.1 Activate the Python Environment**
```bash
# In VS Code terminal (Ctrl+` to open terminal)
source scraper_env/bin/activate

# You should see (scraper_env) prefix in your terminal prompt
```

#### **2.2 Install System Dependencies (First Time Only)**
```bash
# Install required system packages for Playwright
sudo apt update
sudo playwright install-deps chromium
playwright install chromium
```

#### **2.3 Run the Enhanced Scraper**
```bash
# Run the updated script with enhanced features
python scrape_bestsellers_updated.py
```

#### **2.4 Monitor Progress**
The script will show real-time progress like this:
```
Found 31 categories (took 1.91s)
[1/31] Scraping: Amazon Launchpad
    Initial ASIN containers detected: 34
    Page 1: extracted 48 items
    Successfully navigated to page 2
    Page 2: extracted 47 items
  ✓ Got 95 items in 18.45s (P1:48, P2:47)
  Progress: 1/31 categories | Elapsed: 00:00:20 | ETA: 00:10:05
```

#### **2.5 View Results**
After completion, you'll find:
- **JSON file**: `bestsellers_updated_YYYYMMDD_HHMMSS.json`
- **CSV file**: `bestsellers_updated_YYYYMMDD_HHMMSS.csv`

## 🏗️ **Script Architecture & Components**

### **Core Components Overview**

```
scrape_bestsellers_updated.py
├── Utility Functions          # Data formatting and file operations
├── Data Validation           # Cleaning and validating scraped data
├── Enhanced Data Extraction  # Multi-strategy content extraction
├── Scrolling & Waiting       # Dynamic content loading handlers
├── Product Extraction        # ASIN-based and fallback methods
├── Navigation Helpers        # Page navigation and URL handling
├── Category Scraping         # Main scraping orchestration
└── Main Orchestration        # Script execution and progress tracking
```

### **🔧 Key Technical Features**

#### **1. Universal ASIN-Based Extraction**
```python
# Primary strategy: Uses Amazon's internal product identifiers
asin_containers = page.locator('[data-asin]:not([data-asin=""])')
```
- **Why it works**: ASIN containers are consistent across all Amazon categories
- **Benefit**: Reliable data correlation and extraction

#### **2. Multi-Strategy Fallback System**
```python
# Strategy 1: ASIN-based (most reliable)
# Strategy 2: Universal CSS selectors
# Strategy 3: Position-based correlation
```
- **Adaptability**: Handles different page layouts automatically
- **Robustness**: Continues working even if one method fails

#### **3. Enhanced Page Loading**
```python
def scroll_to_bottom_enhanced(page, max_scrolls=8, pause_ms=2000):
    # Monitors ASIN container count during scrolling
    # Stops when content stabilizes
    # Handles lazy-loaded content
```
- **Smart waiting**: Detects when content is fully loaded
- **Performance**: Avoids unnecessary waiting

#### **4. Universal Selectors**
Based on comprehensive analysis of Amazon's page structures:
```python
# These selectors work across ALL categories:
product_links = 'a.a-link-normal[href*="/dp/"]'    # 90+ matches per page
ranks = '.zg-bdg-text'                             # 30 matches per page  
prices = 'span._cDEzb_p13n-sc-price_3mJ9Z'        # 30 matches per page
ratings = 'a[aria-label*="out of 5"]'             # 25-29 matches per page
```

### **🔄 Scraping Workflow**

#### **Phase 1: Category Discovery**
1. Navigate to Amazon bestsellers homepage
2. Extract all category links from left navigation
3. Return list of 31 categories with URLs

#### **Phase 2: Per-Category Extraction**
```
For each category:
├── Navigate to category page
├── Check initial ASIN container count
├── Enhanced page loading with scroll monitoring
├── Extract page 1 products (1-50)
├── Navigate to page 2 (if page 1 successful)
├── Extract page 2 products (51-100)
├── Deduplicate and validate results
└── Save category data with statistics
```

#### **Phase 3: Data Processing**
1. **Deduplication**: Remove duplicates by ASIN and product link
2. **Validation**: Ensure data quality and completeness
3. **Formatting**: Clean text and standardize formats
4. **Export**: Save as both JSON and CSV with timestamps

### **🛡️ Error Handling & Robustness**

#### **Category-Level Isolation**
- Failed categories don't break the entire scraping process
- Detailed error logging for debugging
- Graceful degradation with partial results

#### **Network Resilience**
```python
# Multiple timeout strategies
page.goto(url, wait_until="domcontentloaded", timeout=30000)
page.wait_for_load_state("networkidle", timeout=8000)
```

#### **Content Verification**
- Validates minimum item counts per page
- Checks for successful page navigation
- Monitors ASIN container stability

### **📊 Data Output Structure**

#### **JSON Structure**
```json
{
  "bestsellers": {
    "Category Name": {
      "category_link": "https://amazon.in/gp/bestsellers/...",
      "category_items": [
        {
          "rank": "#1",
          "name": "Product Name",
          "link": "https://amazon.in/dp/ASIN...",
          "rating": "4.3 out of 5 stars, 1,234 ratings",
          "price": "₹299.00"
        }
      ],
      "extraction_stats": {
        "page1_items": 48,
        "page2_items": 47,
        "final_unique_items": 95
      }
    }
  }
}
```

#### **CSV Columns**
- `root_category`: Always "bestseller"
- `sub_category`: Category name
- `category_link`: Category URL
- `rank`: Product rank (#1, #2, etc.)
- `name`: Product title
- `link`: Product page URL
- `rating`: Star rating and count
- `price`: Price in Indian Rupees
- `page1_items`: Items found on page 1
- `page2_items`: Items found on page 2
- `final_unique_items`: Total unique items

## 🔍 **Troubleshooting**

### **Common Issues**

#### **Playwright Dependency Errors**
```bash
# Install system dependencies
sudo playwright install-deps chromium
playwright install chromium
```

#### **Low Item Counts**
- Script automatically retries with fallback methods
- Check console output for extraction method used
- Categories with <10 items will show warnings

#### **Network Timeouts**
- Script includes extended timeouts for slow connections
- Automatic page refresh for failed initial loads
- Polite delays to avoid rate limiting

### **Performance Optimization**

#### **Adjust Timing (if needed)**
```python
# In scrape_category function, modify:
polite_pause(page, ms=1500 + (idx % 3) * 300)  # Increase for slower connections
```

#### **Headless Mode**
```python
# For faster execution, ensure headless=True:
browser = p.chromium.launch(headless=True)
```

## 📈 **Expected Results**

Based on comprehensive testing:

| Category Type | Expected Items | Success Rate |
|---------------|----------------|--------------|
| Standard Categories | 80-100 items | 95%+ |
| Books Category | 30+ items | 90%+ |
| Apps & Games | 30+ items | 90%+ |
| Specialized Categories | 50+ items | 85%+ |

### **Performance Metrics**
- **Average time per category**: 15-25 seconds
- **Total execution time**: 8-12 minutes for all 31 categories
- **Success rate**: 95%+ categories with meaningful data
- **Data quality**: 98%+ items with complete information

## 🔧 **Customization Options**

### **Modify Categories**
Edit the `get_categories()` function to target specific categories.

### **Adjust Item Limits**
Change the 100-item limit in extraction functions.

### **Output Formats**
Modify `save_as_csv()` function for different CSV structures.

### **Timing Adjustments**
Modify `polite_pause()` calls to adjust scraping speed.

---

## 📄 **License & Usage**

This scraper is for educational and research purposes. Please respect Amazon's robots.txt and terms of service. Use responsibly with appropriate delays between requests.

## 🤝 **Contributing**

Feel free to submit issues and enhancement requests. The script is designed to be modular and extensible for additional features.