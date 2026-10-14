"""
EcoPackAI - Database Models (SQLAlchemy ORM)
Module: Flask Backend - Data Persistence

Tables
    materials               packaging material catalogue (data/processed/materials.csv)
    products                products to package (data/processed/products.csv)
    recommendation_runs     one row per /recommend call (product, mode, model versions)
    recommendation_logs     ranked materials of a run: links products <-> materials
    prediction_history      one row per material predicted by /predict

Column names and types match data/processed/*.csv and the data dictionary
(docs/data_dictionary.md is generated from these definitions). Every column
carries a comment, which is also stored in PostgreSQL.

The schema is created and versioned with Alembic (backend/migrations/).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _number(comment: str):
    return mapped_column(Float, nullable=False, comment=comment)


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = {"comment": "Packaging material catalogue (403 materials)"}

    material_id: Mapped[str] = mapped_column(String(20), primary_key=True,
                                             comment="Unique material identifier, e.g. MAT_0001")
    packaging_type: Mapped[str] = mapped_column(String(100), nullable=False,
                                                comment="Specific packaging form (6 values)")
    material_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                               comment="Cardboard, Plastic, Paper/Bio-Based or Steel")
    suitable_product_categories: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Comma-separated product groups the material suits")
    recommended_packaging_use_cases: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Typical use case (free text)")
    supplier_region: Mapped[str] = mapped_column(String(50), nullable=False,
                                                 comment="EMEA, APAC, AMERICAS, ROW, LATAM or EU")
    recyclability_percent: Mapped[float] = _number("% of material recyclable (0-100)")
    recyclability_category: Mapped[str] = mapped_column(String(20), nullable=False,
                                                        comment="Low, Medium or High")
    recycled_content_percent: Mapped[float] = _number("% made from recycled input (0-100)")
    reusability_percent: Mapped[float] = _number("% reuse potential (0-100)")
    biodegradation_time_days: Mapped[float] = _number("Days to decompose")
    end_of_life_disposal_percent: Mapped[float] = _number("% sent to disposal (0-100)")
    carbon_footprint_kg_co2_per_unit: Mapped[float] = _number("CO2 per packaging unit (kg)")
    co2_emission_per_kg: Mapped[float] = _number("CO2 per kg of material (target of the CO2 model)")
    waste_reduction_impact_percent: Mapped[float] = _number("Estimated waste reduction (0-100)")
    sustainability_target_progress_percent: Mapped[float] = _number("Progress toward sustainability goals (0-100)")
    load_handling_score: Mapped[float] = _number("Load-bearing capability (1-10)")
    moisture_resistance_score: Mapped[float] = _number("Resistance to moisture (1-10)")
    thermal_resistance_score: Mapped[float] = _number("Resistance to temperature (1-10)")
    cost_per_unit_usd: Mapped[float] = _number("Price per packaging unit in USD (target of the cost model)")
    annual_usage_units: Mapped[float] = _number("Units used annually")
    total_material_weight_tons: Mapped[float] = _number("Total annual material weight (tons)")
    supplier_sustainability_compliance_percent: Mapped[float] = _number("Supplier compliance rating (0-100)")

    recommendations: Mapped[list["RecommendationLog"]] = relationship(back_populates="material")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"comment": "Products to package (1,500 products)"}

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
                                            comment="Unique product identifier")
    product_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Product name")
    category: Mapped[str] = mapped_column(String(100), nullable=False,
                                          comment="Food, Electronics, Cosmetics, Paper Product, Pharmacy or Drinkware")
    product_weight_kg: Mapped[float] = _number("Net product weight (kg)")
    fragility_index: Mapped[int] = mapped_column(Integer, nullable=False,
                                                 comment="Handling care required, 1 (low) to 5 (high)")
    shipping_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="Air, Road or Sea")

    recommendations: Mapped[list["RecommendationLog"]] = relationship(back_populates="product")
    runs: Mapped[list["RecommendationRun"]] = relationship(back_populates="product")

    def as_ranking_input(self) -> dict:
        return {"product_id": self.product_id, "product_name": self.product_name, "category": self.category,
                "product_weight_kg": self.product_weight_kg, "fragility_index": self.fragility_index,
                "shipping_type": self.shipping_type}


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    __table_args__ = {"comment": "One row per /recommend request"}

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="Run identifier")
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                            comment="API request ID (X-Request-ID)")
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.product_id"), nullable=True, index=True,
        comment="Product from the products table; NULL for a product sent inline")
    product_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False,
                                                   comment="Product attributes used for the ranking")
    mode: Mapped[str] = mapped_column(String(30), nullable=False,
                                      comment="balanced, sustainability_first or cost_first")
    top_n: Mapped[int] = mapped_column(Integer, nullable=False, comment="Number of materials requested")
    n_candidates: Mapped[int] = mapped_column(Integer, nullable=False,
                                              comment="Materials that passed the business constraints")
    status: Mapped[str] = mapped_column(String(30), nullable=False, comment="ok or no_valid_material")
    cost_model_version: Mapped[str] = mapped_column(String(50), nullable=False,
                                                    comment="Cost model name and version")
    co2_model_version: Mapped[str] = mapped_column(String(50), nullable=False,
                                                   comment="CO2 model name and version")
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                         comment="True if served from the response cache")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 nullable=False, comment="When the run happened")

    product: Mapped[Optional[Product]] = relationship(back_populates="runs")
    results: Mapped[list["RecommendationLog"]] = relationship(back_populates="run",
                                                              order_by="RecommendationLog.material_rank")


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"
    __table_args__ = {"comment": "Ranked materials per recommendation run (links products and materials)"}

    rec_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
                                        comment="Unique identifier for each recommendation record")
    run_id: Mapped[int] = mapped_column(ForeignKey("recommendation_runs.run_id", ondelete="CASCADE"),
                                        nullable=False, index=True, comment="Run this result belongs to")
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.product_id"), nullable=True, index=True,
        comment="Product the recommendation is for (NULL for an inline product)")
    recommended_material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.material_id"), nullable=False, index=True, comment="Recommended material")
    cost_prediction: Mapped[float] = _number("Predicted cost per unit (USD) from the Random Forest model")
    co2_prediction: Mapped[float] = _number("Predicted CO2 per kg from the XGBoost model")
    final_score: Mapped[float] = _number("Weighted ranking score (0-100)")
    material_rank: Mapped[int] = mapped_column(Integer, nullable=False, comment="1 = best")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 nullable=False, comment="When the recommendation was generated")

    run: Mapped[RecommendationRun] = relationship(back_populates="results")
    product: Mapped[Optional[Product]] = relationship(back_populates="recommendations")
    material: Mapped[Material] = relationship(back_populates="recommendations")


class PredictionHistory(Base):
    __tablename__ = "prediction_history"
    __table_args__ = {"comment": "One row per material predicted by /predict"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="Row identifier")
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                            comment="API request ID (X-Request-ID)")
    material_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="material_id sent by the client (may be a new material)")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                            comment="SHA-256 of the material attributes")
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, comment="Material attributes sent")
    predicted_cost_usd: Mapped[float] = _number("Predicted cost per unit (USD)")
    predicted_co2_per_kg: Mapped[float] = _number("Predicted CO2 per kg")
    cost_model_version: Mapped[str] = mapped_column(String(50), nullable=False,
                                                    comment="Cost model name and version")
    co2_model_version: Mapped[str] = mapped_column(String(50), nullable=False,
                                                   comment="CO2 model name and version")
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                         comment="True if served from the response cache")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 nullable=False, comment="When the prediction was made")


ALL_MODELS = [Material, Product, RecommendationRun, RecommendationLog, PredictionHistory]
