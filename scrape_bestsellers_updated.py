# scrape_bestsellers_updated.py
# Enhanced Amazon Bestsellers Scraper with Universal Selectors and Robust Error Handling
# Based on comprehensive analysis of Amazon's category page structures

import json
import time
import re
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import csv

BASE_URL = "https://www.amazon.in"
BESTSELLERS_URL = f"{BASE_URL}/gp/bestsellers/"

# -----------------------
# Utility helpers
# -----------------------


def format_duration(seconds):
    """Convert seconds to human-readable format (HH:MM:SS)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def save_as_csv(data, filename_prefix="bestsellers"):
    """Convert the scraped data to CSV format."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{filename_prefix}_{ts}.csv"

    csv_rows = []
    bestsellers_data = data.get("bestsellers", {})

    for sub_category, category_data in bestsellers_data.items():
        category_link = category_data.get("category_link", "")
        category_items = category_data.get("category_items", [])
        extraction_stats = category_data.get("extraction_stats", {})

        for item in category_items:
            row = {
                "root_category": "bestseller",
                "sub_category": sub_category,
                "category_link": category_link,
                "rank": item.get("rank", ""),
                "name": item.get("name", ""),
                "link": item.get("link", ""),
                "rating": item.get("rating", ""),
                "price": item.get("price", ""),
                "page1_items": extraction_stats.get("page1_items", ""),
                "page2_items": extraction_stats.get("page2_items", ""),
                "final_unique_items": extraction_stats.get("final_unique_items", ""),
            }
            csv_rows.append(row)

    if csv_rows:
        fieldnames = [
            "root_category",
            "sub_category",
            "category_link",
            "rank",
            "name",
            "link",
            "rating",
            "price",
            "page1_items",
            "page2_items",
            "final_unique_items",
        ]

        with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        print(f"CSV saved to: {csv_filename}")
        return csv_filename
    else:
        print("No data to save as CSV")
        return None


def clean_text(s: str | None) -> str:
    """Clean and normalize text content."""
    if not s:
        return ""
    # Collapse whitespace/newlines and strip
    return " ".join(s.split()).strip()


def polite_pause(page, ms=1000):
    """Polite pause for rate limiting."""
    page.wait_for_timeout(ms)


# -----------------------
# Data validation and cleaning helpers
# -----------------------


def validate_and_clean_items(items):
    """
    Validate and clean extracted product data to ensure quality.
    """
    validated_items = []

    for item in items:
        # Essential field validation
        if not item.get("name") or not item.get("link"):
            continue  # Skip items without essential data

        # Clean and validate each field
        validated_item = {
            "rank": clean_rank(item.get("rank", "")),
            "name": clean_product_name(item.get("name", "")),
            "link": validate_product_link(item.get("link", "")),
            "rating": clean_rating(item.get("rating", "")),
            "price": clean_price(item.get("price", "")),
        }

        # Final validation - ensure we have meaningful data
        if (
            validated_item["name"]
            and validated_item["link"]
            and len(validated_item["name"]) > 10
        ):
            validated_items.append(validated_item)

    # Remove duplicates based on product link
    seen_links = set()
    unique_items = []
    for item in validated_items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_items.append(item)

    return unique_items


def clean_rank(rank_text):
    """Clean rank text (e.g., '#1' from 'Best Sellers Rank #1' or '#1')."""
    if not rank_text:
        return ""
    match = re.search(r"#?(\d+)", rank_text)
    return f"#{match.group(1)}" if match else ""


def clean_product_name(name):
    """Clean product name text."""
    if not name:
        return ""
    # Remove excessive whitespace and truncate if too long
    cleaned = clean_text(name)
    return cleaned[:500] if len(cleaned) > 500 else cleaned


def validate_product_link(link):
    """Validate product link format."""
    if not link or "/dp/" not in link:
        return ""
    return link


def clean_rating(rating_text):
    """Clean rating text."""
    if not rating_text:
        return ""
    # Ensure consistent format
    return clean_text(rating_text)[:100]


def clean_price(price_text):
    """Clean price text."""
    if not price_text:
        return ""
    return clean_text(price_text)


# -----------------------
# Enhanced data extraction helpers
# -----------------------


def extract_rating_from_container(container):
    """
    Extract rating information using multiple fallback strategies.
    """
    rating_strategies = [
        # Strategy 1: aria-label from rating link (most reliable based on analysis)
        {"selector": 'a[aria-label*="out of 5"]', "method": "aria_label"},
        # Strategy 2: Star icon with text
        {"selector": ".a-icon-star-small", "method": "star_icon"},
        # Strategy 3: Rating text spans
        {"selector": '[class*="rating"]', "method": "text_content"},
        # Strategy 4: Any element with rating patterns
        {
            "selector": "*",
            "method": "text_pattern",
            "pattern": r"(\d+\.?\d*)\s*out\s*of\s*5",
        },
    ]

    for strategy in rating_strategies:
        try:
            elements = container.locator(strategy["selector"])

            if strategy["method"] == "aria_label":
                for i in range(min(elements.count(), 3)):  # Check first 3 matches
                    aria_label = elements.nth(i).get_attribute("aria-label")
                    if aria_label and "out of 5" in aria_label:
                        return clean_text(aria_label)

            elif strategy["method"] == "star_icon":
                # Look for star icon with adjacent text
                if elements.count() > 0:
                    star_parent = elements.first.locator("xpath=..")
                    text = clean_text(star_parent.inner_text())
                    if text and ("out of" in text or "rating" in text.lower()):
                        return text

            elif strategy["method"] == "text_content":
                for i in range(min(elements.count(), 3)):
                    text = clean_text(elements.nth(i).inner_text())
                    if text and ("out of" in text or "star" in text.lower()):
                        return text

            elif strategy["method"] == "text_pattern":
                container_text = clean_text(container.inner_text())
                match = re.search(strategy["pattern"], container_text, re.IGNORECASE)
                if match:
                    return f"{match.group(1)} out of 5 stars"

        except Exception as e:
            continue  # Try next strategy

    return ""  # No rating found


def extract_price_from_container(container):
    """
    Extract price information using multiple fallback strategies.
    """
    price_strategies = [
        # Strategy 1: Current CSS selectors (proven to work)
        "span._cDEzb_p13n-sc-price_3mJ9Z",
        # Strategy 2: Generic price classes
        ".a-price-whole",
        ".a-price .a-offscreen",
        '[class*="price"]:not([class*="strike"])',
        # Strategy 3: Text pattern matching
        "text_pattern",
    ]

    for strategy in price_strategies:
        try:
            if strategy == "text_pattern":
                # Extract price using regex pattern
                container_text = clean_text(container.inner_text())
                # Pattern for Indian Rupees: ₹1,234.00 or Rs 1,234
                price_pattern = r"(?:₹|Rs\.?\s*)([0-9,]+(?:\.[0-9]{2})?)"
                match = re.search(price_pattern, container_text)
                if match:
                    return f"₹{match.group(1)}"
            else:
                elements = container.locator(strategy)
                if elements.count() > 0:
                    price_text = clean_text(elements.first.inner_text())
                    if price_text and ("₹" in price_text or "Rs" in price_text):
                        return price_text

        except Exception as e:
            continue  # Try next strategy

    return ""  # No price found


# -----------------------
# Enhanced scrolling and waiting
# -----------------------


def scroll_to_bottom_enhanced(page, max_scrolls=8, pause_ms=2000):
    """
    Enhanced scrolling that monitors ASIN container count for completion.
    """
    print("      Starting enhanced page loading...")

    # Wait for initial page structure
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
        print("      Network idle achieved")
    except:
        print("      Network idle timeout, proceeding with scroll")
        page.wait_for_load_state("domcontentloaded", timeout=15000)

    # Progressive scroll with container monitoring
    last_asin_count = 0
    stable_iterations = 0

    for scroll_num in range(max_scrolls):
        # Scroll to bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)

        # Check current ASIN container count
        current_asin_count = page.locator('[data-asin]:not([data-asin=""])').count()

        if current_asin_count > last_asin_count:
            print(
                f"      Scroll {scroll_num + 1}: {current_asin_count} ASIN containers"
            )
            last_asin_count = current_asin_count
            stable_iterations = 0
        else:
            stable_iterations += 1
            print(
                f"      Scroll {scroll_num + 1}: {current_asin_count} containers (stable)"
            )

        # Stop if content has been stable for 2 iterations and we have reasonable content
        if stable_iterations >= 2 and current_asin_count >= 20:
            print("      Content stabilized, stopping scroll")
            break

        # If very few containers after several scrolls, wait longer
        if current_asin_count < 10 and scroll_num >= 3:
            print("      Low container count, extending wait...")
            page.wait_for_timeout(2000)

    final_count = page.locator('[data-asin]:not([data-asin=""])').count()
    print(f"      Enhanced loading complete: {final_count} ASIN containers")

    return final_count


# -----------------------
# Core product extraction methods
# -----------------------


def extract_from_asin_containers_universal(asin_containers):
    """
    Extract using ASIN containers with universal selectors proven to work across categories.
    Based on selector analysis showing these work for Books, Apps & Games, and other categories.
    """
    items = []
    container_count = asin_containers.count()

    for i in range(min(container_count, 100)):
        try:
            container = asin_containers.nth(i)
            asin = container.get_attribute("data-asin")

            # Universal product name and link extraction
            name = ""
            link = ""

            # Use the universal selector: a.a-link-normal[href*="/dp/"] (90 matches in analysis)
            link_elements = container.locator('a.a-link-normal[href*="/dp/"]')

            if link_elements.count() > 0:
                # Get the first valid link element that contains product name
                for j in range(link_elements.count()):
                    link_elem = link_elements.nth(j)
                    potential_name = clean_text(link_elem.inner_text())
                    href = link_elem.get_attribute("href")

                    # Filter out rating links and other non-product links
                    # Product names should be substantial (>15 chars) and not contain only rating info
                    if (
                        potential_name
                        and len(potential_name) > 15
                        and href
                        and not re.search(r"^\d+\.?\d*\s*out\s*of\s*5", potential_name)
                        and "star" not in potential_name.lower()
                    ):
                        name = potential_name
                        link = urljoin(BASE_URL, href)
                        break

            # Universal rank extraction (.zg-bdg-text works everywhere - 30 matches)
            rank = ""
            rank_elem = container.locator(".zg-bdg-text").first
            if rank_elem.count() > 0:
                rank = clean_text(rank_elem.inner_text())

            # Universal rating extraction (a[aria-label*="out of 5"] - 25-29 matches)
            rating = ""
            rating_elem = container.locator('a[aria-label*="out of 5"]').first
            if rating_elem.count() > 0:
                rating = clean_text(rating_elem.get_attribute("aria-label"))

            # Universal price extraction (span._cDEzb_p13n-sc-price_3mJ9Z - 30 matches)
            price = ""
            price_elem = container.locator("span._cDEzb_p13n-sc-price_3mJ9Z").first
            if price_elem.count() > 0:
                price = clean_text(price_elem.inner_text())

            # Only add items with essential data
            if name and link and len(name) > 15:  # Ensure we have a real product name
                items.append(
                    {
                        "rank": rank,
                        "name": name,
                        "link": link,
                        "rating": rating,
                        "price": price,
                        "asin": asin,  # Keep for deduplication
                    }
                )

        except Exception as e:
            print(f"      Warning: Container {i} extraction failed: {e}")
            continue

    return items


def extract_using_universal_selectors(page):
    """
    Fallback method using universal selectors without container correlation.
    Less reliable but works when ASIN method fails.
    """
    items = []

    # Get all product links (universal selector - 90 matches in analysis)
    product_links = page.locator('a.a-link-normal[href*="/dp/"]')
    rank_badges = page.locator(".zg-bdg-text")  # 30 matches
    price_spans = page.locator("span._cDEzb_p13n-sc-price_3mJ9Z")  # 30 matches
    rating_links = page.locator('a[aria-label*="out of 5"]')  # 25-29 matches

    link_count = product_links.count()
    print(f"      Universal fallback: {link_count} product links found")

    # Filter to get actual product name links (not rating links, etc.)
    valid_product_links = []
    for i in range(link_count):
        try:
            link_elem = product_links.nth(i)
            text = clean_text(link_elem.inner_text())
            href = link_elem.get_attribute("href")

            # Filter criteria: meaningful text length, valid href, not a rating link
            if (
                text
                and len(text) > 15
                and href
                and "/dp/" in href
                and not re.search(r"^\d+\.?\d*\s*out\s*of\s*5", text)
                and "star" not in text.lower()
            ):
                valid_product_links.append(
                    {
                        "element": link_elem,
                        "name": text,
                        "link": urljoin(BASE_URL, href),
                        "index": i,
                    }
                )
        except:
            continue

    print(f"      Filtered to {len(valid_product_links)} valid product links")

    # Extract data for valid products (up to 50 per page)
    for idx, product_data in enumerate(valid_product_links[:50]):
        try:
            # Rank (try to correlate by position)
            rank = ""
            if rank_badges.count() > idx:
                rank = clean_text(rank_badges.nth(idx).inner_text())

            # Price (try to correlate by position)
            price = ""
            if price_spans.count() > idx:
                price = clean_text(price_spans.nth(idx).inner_text())

            # Rating (try to correlate by position)
            rating = ""
            if rating_links.count() > idx:
                rating = clean_text(rating_links.nth(idx).get_attribute("aria-label"))

            items.append(
                {
                    "rank": rank,
                    "name": product_data["name"],
                    "link": product_data["link"],
                    "rating": rating,
                    "price": price,
                }
            )

        except Exception as e:
            continue

    return items


def extract_products_on_page(page):
    """
    Universal product extraction using the most reliable selectors found across all categories.
    Uses ASIN containers with proven universal selectors.
    """
    # Enhanced scroll and wait
    final_container_count = scroll_to_bottom_enhanced(page)

    items = []

    # Method 1: ASIN-based extraction (Universal - works everywhere)
    asin_containers = page.locator('[data-asin]:not([data-asin=""])')
    container_count = asin_containers.count()

    print(f"      Found {container_count} ASIN containers")

    if container_count >= 10:
        items = extract_from_asin_containers_universal(asin_containers)
        print(f"      ASIN method: {len(items)} items extracted")

    # Method 2: Fallback using universal selectors (if ASIN method fails)
    if len(items) < 15:  # Threshold for insufficient data
        print(
            f"      ASIN method insufficient ({len(items)} items), using universal fallback"
        )
        fallback_items = extract_using_universal_selectors(page)
        if len(fallback_items) > len(items):
            items = fallback_items
            print(f"      Universal method: {len(items)} items extracted")

    # Final validation and cleanup
    validated_items = validate_and_clean_items(items)
    print(f"      Final validated items: {len(validated_items)}")

    return validated_items


# -----------------------
# Navigation helpers
# -----------------------


def navigate_to_next_page(page):
    """
    Enhanced next page navigation with multiple strategies.
    """
    navigation_strategies = [
        # Strategy 1: Text-based navigation (most reliable)
        lambda: page.get_by_text("Next page").click(timeout=5000),
        # Strategy 2: Specific next page link
        lambda: page.locator('a[href*="pg=2"]').first.click(timeout=5000),
        # Strategy 3: Generic pagination link
        lambda: page.locator('a[href*="pg="]:has-text("Next")').first.click(
            timeout=5000
        ),
        # Strategy 4: Arrow or symbol navigation
        lambda: page.locator('a[href*="pg="] .a-icon-next').first.click(timeout=5000),
        # Strategy 5: Direct URL navigation (backup)
        lambda: navigate_by_url_modification(page),
    ]

    for i, strategy in enumerate(navigation_strategies):
        try:
            print(f"        Trying navigation strategy {i+1}")
            strategy()

            # Wait for navigation to complete
            page.wait_for_load_state("domcontentloaded", timeout=10000)

            # Verify we're on page 2 by checking URL or content
            current_url = page.url
            if "pg=2" in current_url or "page=2" in current_url:
                print(f"        Navigation successful (URL confirmation)")
                return True

            # Alternative verification: check if ASIN containers reloaded
            page.wait_for_timeout(2000)
            new_containers = page.locator('[data-asin]:not([data-asin=""])').count()
            if new_containers >= 10:
                print(f"        Navigation successful (content confirmation)")
                return True

        except Exception as e:
            print(f"        Strategy {i+1} failed: {str(e)}")
            continue

    print(f"        All navigation strategies failed")
    return False


def navigate_by_url_modification(page):
    """
    Backup navigation by modifying URL directly.
    """
    current_url = page.url

    if "pg=" in current_url:
        # Replace existing page parameter
        new_url = current_url.replace("pg=1", "pg=2")
        if new_url == current_url:  # If no pg=1 found, add pg=2
            separator = "&" if "?" in current_url else "?"
            new_url = f"{current_url}{separator}pg=2"
    else:
        # Add page parameter
        separator = "&" if "?" in current_url else "?"
        new_url = f"{current_url}{separator}pg=2"

    print(f"        Attempting direct URL navigation to: {new_url}")
    page.goto(new_url, wait_until="domcontentloaded", timeout=15000)


def deduplicate_products(items):
    """
    Advanced deduplication using multiple criteria.
    """
    seen_links = set()
    seen_asins = set()
    unique_items = []

    for item in items:
        link = item.get("link", "")
        asin = item.get("asin", "")

        # Create deduplication key
        dedup_key = None

        if asin and asin not in seen_asins:
            dedup_key = f"asin:{asin}"
            seen_asins.add(asin)
        elif link and link not in seen_links:
            dedup_key = f"link:{link}"
            seen_links.add(link)

        if dedup_key:
            # Remove ASIN from final output (it was just for deduplication)
            clean_item = {k: v for k, v in item.items() if k != "asin"}
            unique_items.append(clean_item)

    return unique_items


# -----------------------
# Category scraping
# -----------------------


def get_categories(page):
    """Scrape category names + links from the left nav."""
    page.goto(BESTSELLERS_URL, wait_until="domcontentloaded")
    # Wait for the left nav UL
    ul_selector = (
        "ul.a-unordered-list.a-nostyle.a-vertical."
        "_p13n-zg-nav-tree-all_style_zg-browse-group__88fbz"
    )
    page.wait_for_selector(ul_selector, timeout=10000)
    anchors = page.locator(f"{ul_selector} li a")

    categories = []
    count = anchors.count()
    for i in range(count):
        a = anchors.nth(i)
        name = clean_text(a.inner_text())
        href = a.get_attribute("href")
        if not name or not href:
            continue
        url = urljoin(BASE_URL, href)
        categories.append({"name": name, "url": url})
    return categories


def scrape_category(page, category):
    """
    Enhanced category scraping with universal selectors and robust error handling.
    Uses ASIN-based extraction with proven universal selectors.
    """
    category_name = category["name"]
    category_url = category["url"]

    print(f"    Navigating to: {category_url}")

    try:
        # Navigate with extended timeout for problematic categories
        page.goto(category_url, wait_until="domcontentloaded", timeout=30000)

        # Initial wait and page assessment
        page.wait_for_timeout(2000)

        # Check if page loaded properly by looking for ASIN containers
        initial_asin_count = page.locator('[data-asin]:not([data-asin=""])').count()
        print(f"    Initial ASIN containers detected: {initial_asin_count}")

        # If very few containers, try refreshing once
        if initial_asin_count < 5:
            print(f"    Low container count, attempting page refresh...")
            page.reload(wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)
            initial_asin_count = page.locator('[data-asin]:not([data-asin=""])').count()
            print(f"    After refresh: {initial_asin_count} ASIN containers")

        # Page 1 extraction (items 1-50)
        print(f"    Extracting page 1 products...")
        first_batch = extract_products_on_page(page)
        print(f"    Page 1: extracted {len(first_batch)} items")

        # Page 2 extraction (items 51-100)
        second_batch = []

        # Try to navigate to page 2
        if (
            len(first_batch) >= 15
        ):  # Only try page 2 if page 1 was reasonably successful
            print(f"    Attempting to navigate to page 2...")

            if navigate_to_next_page(page):
                print(f"    Successfully navigated to page 2")

                # Wait for page 2 to load
                page.wait_for_timeout(2000)

                # Extract page 2 products
                second_batch = extract_products_on_page(page)
                print(f"    Page 2: extracted {len(second_batch)} items")
            else:
                print(f"    Page 2 navigation failed or not available")
        else:
            print(
                f"    Skipping page 2 due to insufficient page 1 results ({len(first_batch)} items)"
            )

        # Combine and deduplicate results
        all_items = first_batch + second_batch

        # Advanced deduplication by ASIN and link
        unique_items = deduplicate_products(all_items)

        # Final validation and limiting
        final_items = unique_items[:100]  # Ensure max 100 items

        print(f"    Final results: {len(final_items)} unique items")

        # Validate minimum expectations
        if len(final_items) < 10:
            print(f"    WARNING: Low item count for {category_name}")

        return {
            "category_link": category_url,
            "category_items": final_items,
            "extraction_stats": {
                "page1_items": len(first_batch),
                "page2_items": len(second_batch),
                "total_before_dedup": len(all_items),
                "final_unique_items": len(final_items),
                "initial_asin_count": initial_asin_count,
            },
        }

    except Exception as e:
        print(f"    ERROR: Failed to scrape {category_name}: {str(e)}")

        # Return minimal structure to avoid breaking the overall process
        return {
            "category_link": category_url,
            "category_items": [],
            "extraction_stats": {
                "error": str(e),
                "page1_items": 0,
                "page2_items": 0,
                "total_before_dedup": 0,
                "final_unique_items": 0,
            },
        }


# -----------------------
# Main orchestration
# -----------------------


def main():
    start_time = time.time()
    result = {"bestsellers": {}}

    with sync_playwright() as p:
        # Headless Chromium; flip to headless=False if you want to watch it run
        browser = p.chromium.launch(headless=False)
        # Using a real browser context helps reduce friction; locale en-IN
        context = browser.new_context(locale="en-IN")
        page = context.new_page()

        print("Loading categories…")
        categories_start = time.time()
        categories = get_categories(page)
        categories_time = time.time() - categories_start
        print(f"Found {len(categories)} categories (took {categories_time:.2f}s)")

        total_items = 0
        successful_categories = 0
        failed_categories = 0

        for idx, cat in enumerate(categories, start=1):
            try:
                category_start = time.time()
                print(f"[{idx}/{len(categories)}] Scraping: {cat['name']}")

                data = scrape_category(page, cat)
                result["bestsellers"][cat["name"]] = data

                category_time = time.time() - category_start
                items_count = len(data.get("category_items", []))
                total_items += items_count

                if items_count > 0:
                    successful_categories += 1
                    status = "✓"
                else:
                    failed_categories += 1
                    status = "✗"

                # Show extraction stats
                stats = data.get("extraction_stats", {})
                page1_items = stats.get("page1_items", 0)
                page2_items = stats.get("page2_items", 0)

                print(
                    f"  {status} Got {items_count} items in {category_time:.2f}s (P1:{page1_items}, P2:{page2_items})"
                )

                # Calculate and display progress
                elapsed = time.time() - start_time
                avg_time_per_category = elapsed / idx
                estimated_total = avg_time_per_category * len(categories)
                remaining_time = estimated_total - elapsed

                print(
                    f"  Progress: {idx}/{len(categories)} categories | "
                    f"Elapsed: {format_duration(elapsed)} | "
                    f"ETA: {format_duration(remaining_time)}"
                )

                # Be a polite guest
                polite_pause(page, ms=1500 + (idx % 3) * 300)

            except Exception as e:
                category_time = time.time() - category_start
                failed_categories += 1
                print(
                    f"  ✗ Error scraping {cat['name']} after {category_time:.2f}s: {e}"
                )

        browser.close()

    # Save JSON with timestamped filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bestsellers_updated_{ts}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Calculate final timing statistics
    total_time = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"ENHANCED SCRAPING COMPLETED")
    print(f"{'='*60}")
    print(f"Total time: {format_duration(total_time)}")
    print(f"Categories processed: {successful_categories}/{len(categories)} successful")
    print(f"Failed categories: {failed_categories}")
    print(f"Total items scraped: {total_items}")
    print(f"Average time per category: {total_time/len(categories):.2f}s")
    print(f"Average items per second: {total_items/total_time:.2f}")
    print(f"JSON saved to: {filename}")

    # Also save as CSV
    csv_start = time.time()
    csv_file = save_as_csv(result, "bestsellers_updated")
    csv_time = time.time() - csv_start

    if csv_file:
        print(f"CSV saved to: {csv_file} (took {csv_time:.2f}s)")

    # Summary of improvements
    print(f"\n{'='*60}")
    print(f"ENHANCEMENT SUMMARY")
    print(f"{'='*60}")
    print(f"• Universal ASIN-based extraction")
    print(f"• Multi-strategy fallback selectors")
    print(f"• Enhanced page loading detection")
    print(f"• Advanced deduplication logic")
    print(f"• Robust error handling per category")
    print(f"• Detailed extraction statistics")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
