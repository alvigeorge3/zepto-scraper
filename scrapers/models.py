from typing import TypedDict, Optional

class ProductItem(TypedDict):
    # Platform identification
    platform: str
    
    # Category information
    category: str
    subcategory: str  # NEW: Primary subcategory name
    clicked_label: str  # NEW: Category/subcategory label that was clicked
    
    # Product information
    name: str
    brand: str
    base_product_id: Optional[str]  # NEW: Unique product ID
    group_id: Optional[str]  # NEW: Product group ID (Blinkit-specific)
    merchant_type: Optional[str]  # NEW: Merchant type (Blinkit-specific)
    
    # Pricing
    price: float
    mrp: float
    
    # Product details
    weight: str
    shelf_life_in_hours: Optional[int]  # NEW: Product shelf life (if available)
    
    # Availability
    availability: str
    inventory: Optional[int]  # NEW: Available quantity/stock level
    
    # Delivery
    eta: str
    store_id: Optional[str]
    
    # URLs
    image_url: str
    product_url: str
    
    # Metadata
    scraped_at: str
    pincode_input: str  # NEW: Pincode used for query

class AvailabilityResult(TypedDict):
    input_pincode: str
    url: str
    platform: str
    name: str # Enriched from page if possible
    price: float
    mrp: float
    availability: str # "In Stock", "Out of Stock", "Unknown"
    
    # Detailed fields for Availability Scraping Mode
    seller_details: Optional[str]
    manufacturer_details: Optional[str]
    marketer_details: Optional[str]
    variant_count: Optional[int]
    variant_in_stock_count: Optional[int]
    inventory: Optional[int]
    
    scraped_at: str
    error: Optional[str]
