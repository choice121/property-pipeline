from sqlalchemy import Column, String, Integer, Float, Boolean, Text
from sqlalchemy.sql import func
from database.db import Base


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    source_url = Column(String)
    source_listing_id = Column(String)

    status = Column(String, default="scraped")

    title = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zip = Column(String)
    county = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    bedrooms = Column(Integer)
    bathrooms = Column(Float)
    half_bathrooms = Column(Integer)
    square_footage = Column(Integer)
    lot_size_sqft = Column(Integer)
    monthly_rent = Column(Integer)
    property_type = Column(String)
    year_built = Column(Integer)
    description = Column(Text)
    available_date = Column(String)
    parking = Column(String)
    pets_allowed = Column(Boolean)
    pet_details = Column(Text)
    smoking_allowed = Column(Boolean)
    lease_terms = Column(Text)
    amenities = Column(Text)
    appliances = Column(Text)
    utilities_included = Column(Text)
    flooring = Column(Text)
    heating_type = Column(String)
    cooling_type = Column(String)
    laundry_type = Column(String)
    virtual_tour_url = Column(String)

    original_image_urls = Column(Text)
    local_image_paths = Column(Text, default="[]")

    original_data = Column(Text)
    edited_fields = Column(Text, default="[]")

    published_at = Column(String)
    choice_property_id = Column(String)

    scraped_at = Column(String, default=func.now())
    updated_at = Column(String, default=func.now())
