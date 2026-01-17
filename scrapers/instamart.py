
import asyncio
import logging
import json
import re
import time
from typing import List
from .base import BaseScraper
from .models import ProductItem, AvailabilityResult
from playwright.async_api import TimeoutError

logger = logging.getLogger(__name__)

class InstamartScraper(BaseScraper):
    def __init__(self, headless=False):
        super().__init__(headless)
        self.base_url = "https://www.swiggy.com/instamart"
        self.delivery_eta = "N/A"

    async def start(self):
        # We need to customize the context creation to include permissions
        # So we can't just call super().start() directly if we want to pass specific context args
        # But BaseScraper.start() creates context.
        # Let's completely override start for Instamart to handle Geolocation custom logic
        # OR we can update BaseScraper. But overriding here is safer for now to avoid breaking others.
        
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        
        # Launch browser (similar to BaseScraper but we can simple it down or use same logic)
        # For simplicity, just launch chromium/msedge
        browsers_to_try = [
            {'channel': 'msedge'},
            {'channel': 'chrome'},
            {}, 
        ]
        
        for browser_kwargs in browsers_to_try:
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=self.headless, 
                    **browser_kwargs
                )
                break
            except Exception:
                continue
                
        if not self.browser:
            raise Exception("Failed to launch any browser")

        # Create context with Geolocation
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            permissions=['geolocation'],
            geolocation={'latitude': 12.9716, 'longitude': 77.5946}, # Bangalore
            locale='en-IN'
        )
        self.page = await self.context.new_page()
        
        # Resource blocking
        await self.page.route("**/*", self._handle_route)

    async def _handle_route(self, route):
        if route.request.resource_type in ["image", "media", "font"]:
            await route.abort()
        else:
            await route.continue_()

    async def set_location(self, pincode: str):
        logger.info(f"Setting location to {pincode}")
        try:
            await self.page.goto(self.base_url, timeout=60000, wait_until='domcontentloaded')
            await self.page.wait_for_timeout(3000)

            # Debugging: Screenshot before interaction
            await self.page.screenshot(path="debug_instamart_pre_click.png")

            # 1. Trigger Location Modal
            logger.info("Clicking location trigger...")


            # CHECK FOR ERROR PAGE
            try:
                if await self.page.is_visible("text='Something went wrong!'", timeout=3000):
                    logger.warning("Detected 'Something went wrong!' error page. Attempting to click Retry...")
                    retry_btn = await self.page.query_selector("button:has-text('Retry')")
                    if retry_btn:
                        await retry_btn.click()
                        await self.page.wait_for_timeout(3000) # Wait for reload
            except:
                pass

            try:
                # Wait for any trigger to be visible
                trigger_selector = "div[data-testid='header-location-container'], span:has-text('Setup your location'), span:has-text('Other'), span:has-text('Location'), button:has-text('Locate Me'), div[data-testid='DEFAULT_ADDRESS_CONTAINER']" 
                try:
                    await self.page.wait_for_selector(trigger_selector, timeout=10000)
                except: 
                    # If timeout, maybe we are already in a state or selectors failed.
                    # Capture screenshot to debug if we fail again
                    pass
                
                triggers = [
                    "div[data-testid='DEFAULT_ADDRESS_CONTAINER']",
                    "div[data-testid='DEFAULT_ADDRESS_TITLE']",
                    "div[data-testid='header-location-container']",
                    "span:has-text('Setup your location')",
                    "span:has-text('Other')",
                    "span:has-text('Location')",
                    "button:has-text('Locate Me')",
                    "div[class*='LocationHeader']"
                ]
                for t in triggers:
                    if await self.page.is_visible(t):
                        # Highlight for debugging
                        try:
                            element = await self.page.query_selector(t)
                            if element:
                                await element.scroll_into_view_if_needed()
                        except: pass
                        
                        logger.info(f"Clicking trigger: {t}")
                        await self.page.click(t)
                        break
            except Exception as e:
                logger.warning(f"Trigger click attempt failed: {e}")

            # 2. Type pincode
            logger.info("Typing pincode...")
            search_input = "input[placeholder*='Search for area'], input[name='location'], input[data-testid='search-input'], input[class*='SearchInput'], input[placeholder*='Enter area']"

            search_input = "input[placeholder*='Search for area'], input[name='location'], input[data-testid='search-input'], input[class*='SearchInput'], input[placeholder*='Enter area']"
            
            await self.page.wait_for_selector(search_input, state="visible", timeout=5000)
            
            valid_input = None
            if await self.page.is_visible("input[data-testid='search-input']"):
                valid_input = "input[data-testid='search-input']"
            else:
                valid_input = search_input 

            await self.page.fill(valid_input, pincode)
            
            # 3. Wait for suggestions
            logger.info("Waiting for suggestions...")
            suggestion = "div[data-testid='location-search-result'], div[class*='SearchResults'] div"
            await self.page.wait_for_selector(suggestion, timeout=10000)
            
            # Click first
            await self.page.click(f"{suggestion} >> nth=0")
            
            # 4. Wait for redirect/reload
            await self.page.wait_for_timeout(3000) 
            
            # 5. Extract ETA from header
            try:
                header_text = await self.page.inner_text("header")
                match = re.search(r'(\d+\s*MINS?)', header_text, re.IGNORECASE)
                if match:
                    self.delivery_eta = match.group(1)
                    logger.info(f"Captured Instamart ETA: {self.delivery_eta}")
            except Exception as e:
                logger.warning(f"Could not extract ETA: {e}")

            logger.info("Location set successfully")
            
        except Exception as e:
            logger.error(f"Error setting location: {e}")
            try:
                await self.page.screenshot(path="error_instamart_location.png")
                content = await self.page.content()
                with open("debug_instamart_fail.html", "w", encoding="utf-8") as f:
                    f.write(content)
            except: pass

    async def scrape_delivery_eta(self):
        try:
            selectors = [
                "div[data-testid='header-delivery-eta']",
                "span[data-testid='eta-container']",
                "div[class*='DeliveryTime']",
                "div[aria-label*='Delivery in']"
            ]
            
            for sel in selectors:
                try:
                    if await self.page.is_visible(sel):
                        text = await self.page.inner_text(sel)
                        if "aria-label" in sel or (await self.page.get_attribute(sel, "aria-label")):
                             val = await self.page.get_attribute(sel, "aria-label")
                             if val: text = val
                        
                        match = re.search(r'(\d+\s*mins?)', text, re.IGNORECASE)
                        if match:
                            return match.group(1).lower()
                except:
                    continue
            return "N/A"
        except Exception as e:
            logger.error(f"Error extracting ETA: {e}")
            return "N/A"

    async def scrape_assortment(self, category_url: str, pincode: str = "N/A") -> List[ProductItem]:
        logger.info(f"Scraping assortment from {category_url}")
        
        results: List[ProductItem] = []
        try:
            await self.page.goto(category_url, timeout=60000, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000) 

            # Scrape ETA using the new robust method
            self.delivery_eta = await self.scrape_delivery_eta()
            logger.info(f"Scraped Assortment ETA: {self.delivery_eta}")
            
            products_map = {}
            
            # Strategy: JSON-LD (Schema.org)
            try:
                ld_scripts = await self.page.query_selector_all('script[type="application/ld+json"]')
                for script in ld_scripts:
                    try:
                        text = await script.inner_text()
                        data = json.loads(text)
                        
                        if isinstance(data, dict) and data.get('@type') == 'ItemList' and 'itemListElement' in data:
                            for item in data['itemListElement']:
                                if item.get('@type') == 'Product':
                                    p_name = item.get('name', 'Unknown')
                                    p_id = item.get('sku') or str(abs(hash(p_name)))
                                    
                                    price = 0.0
                                    offer = item.get('offers', {})
                                    if isinstance(offer, dict):
                                        price = float(offer.get('price', 0))
                                    elif isinstance(offer, list) and offer:
                                        price = float(offer[0].get('price', 0))
                                        
                                    image = "N/A"
                                    if item.get('image'):
                                        imgs = item.get('image')
                                        if isinstance(imgs, list) and imgs: image = imgs[0]
                                        elif isinstance(imgs, str): image = imgs
                                    
                                    products_map[p_id] = {
                                        'id': p_id,
                                        'name': p_name,
                                        'price': price,
                                        'mrp': price, 
                                        'image': image,
                                        'brand': item.get('brand', {}).get('name', 'Unknown'),
                                        'availability': offer.get('availability', 'Unknown')
                                    }
                    except:
                        continue
            except Exception as e:
                logger.warning(f"JSON-LD extraction failed: {e}")

            logger.info(f"Extracted {len(products_map)} unique products from JSON-LD")

            # Extract category and subcategory from URL
            category = "N/A"
            subcategory = "N/A"
            try:
                if "categoryName=" in category_url:
                    category = category_url.split("categoryName=")[1].split("&")[0].replace("%20", " ")
                    subcategory = category  # Instamart URLs don't seem to have separate subcategories
            except:
                pass
            
            clicked_label = f"{category} > {subcategory}" if subcategory != "N/A" else category

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            for pid, p in products_map.items():
                try:
                    # Enrich Weight from Name
                    name = p['name']
                    weight = "N/A"
                    w_match = re.search(r'\(([\d\.]+\s*[kgmlKGML]+)\)', name)
                    if w_match:
                        weight = w_match.group(1)
                    
                    availability = "In Stock" if "InStock" in str(p['availability']) else "Out of Stock"
                    
                    item: ProductItem = {
                        "platform": "instamart",
                        "category": category,
                        "subcategory": subcategory,
                        "clicked_label": clicked_label,
                        "name": name,
                        "brand": p['brand'],
                        "base_product_id": pid,
                        "group_id": None,  # Blinkit-specific
                        "merchant_type": None,  # Blinkit-specific
                        "mrp": p['mrp'], 
                        "price": p['price'],
                        "weight": weight,
                        "shelf_life_in_hours": None,  # Not available in Instamart JSON-LD
                        "eta": self.delivery_eta, 
                        "availability": availability,
                        "inventory": None,  # Not available in Instamart JSON-LD
                        "store_id": "Unknown",
                        "product_url": f"{self.base_url}/item/{pid}",
                        "image_url": p['image'],
                        "scraped_at": timestamp,
                        "pincode_input": pincode
                    }
                    results.append(item)
                except Exception as e:
                    pass
                    
        except Exception as e:
            logger.error(f"Error scraping assortment: {e}")
            await self.page.screenshot(path="error_instamart_assortment.png")
            
        return results

    async def scrape_availability(self, product_url: str) -> AvailabilityResult:
        logger.info(f"Scraping availability from {product_url}")
        
        result: AvailabilityResult = {
             "input_pincode": "",
             "url": product_url,
             "platform": "instamart",
             "name": "N/A",
             "price": 0.0,
             "mrp": 0.0,
             "availability": "Unknown",
             "seller_details": None,
             "manufacturer_details": None,
             "marketer_details": None,
             "variant_count": 1,
             "variant_in_stock_count": 1,
             "inventory": None,
             "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
             "error": None
        }
        
        try:
            await self.page.goto(product_url, timeout=60000, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(3000)

            # 1. JSON-LD Strategy
            try:
                ld_scripts = await self.page.query_selector_all('script[type="application/ld+json"]')
                for script in ld_scripts:
                    try:
                        text = await script.inner_text()
                        data = json.loads(text)
                        
                        product_data = None
                        if isinstance(data, dict):
                            if data.get('@type') == 'Product':
                                product_data = data
                        elif isinstance(data, list):
                            product_data = next((item for item in data if item.get('@type') == 'Product'), None)
                            
                        if product_data:
                            result["name"] = product_data.get('name', 'N/A')
                            
                            offers = product_data.get('offers', {})
                            if isinstance(offers, dict):
                                result["price"] = float(offers.get('price', 0))
                                result["availability"] = "In Stock" if "InStock" in offers.get('availability', '') else "Out of Stock"
                            
                            # Detailed Metadata
                            brand_org = product_data.get('brand', {})
                            if isinstance(brand_org, dict):
                                result["manufacturer_details"] = brand_org.get('name')
                            elif isinstance(brand_org, str):
                                result["manufacturer_details"] = brand_org
                                
                            result["description"] = product_data.get('description') # Store desc for later text mining if needed
                            
                            break
                    except: continue
            except: pass

            # 2. DOM Strategy for Detailed Fields (if JSON incomplete)
            text_content = await self.page.inner_text("body")
            
            def extract_section(keyword):
                try:
                    match = re.search(f"{keyword}\\n(.*?)(?:\\n\\n|\\Z)", text_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        return match.group(1).strip()
                except: pass
                return None

            if not result["manufacturer_details"]:
                result["manufacturer_details"] = extract_section("Manufacturer Details")
            
            result["marketer_details"] = extract_section("Marketed By")
            result["seller_details"] = extract_section("Seller Details")

            # 3. Variants
            # Instamart variants often in a selector
            result["variant_count"] = 1 # Default
            # Attempt to find variant selector
            try:
                # Selector for variant container
                variants = await self.page.query_selector_all("[data-testid='variant-container']") 
                if variants:
                    result["variant_count"] = len(variants)
                    # Count in stock?
            except: pass
            
            # Recalculate stock based on availability string
            if result["availability"] != "In Stock":
                result["variant_in_stock_count"] = 0
            
        except Exception as e:
            logger.error(f"Error scraping availability: {e}")
            result["error"] = str(e)
            
        return result
