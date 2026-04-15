import json
import logging

logger = logging.getLogger(__name__)

APPLICATION_FEE_FLOOR = 50.0

RENT_TIERS = [
    (1500,  0.05),
    (3000,  0.10),
    (float('inf'), 0.15),
]


def _tiered_discount(rent: float) -> float:
    for threshold, rate in RENT_TIERS:
        if rent < threshold:
            return rate
    return RENT_TIERS[-1][1]


def apply_pricing_rules(prop) -> bool:
    changed = False

    if prop.monthly_rent is not None:
        original_rent = float(prop.monthly_rent)
        if original_rent > 0:
            try:
                original_data = json.loads(prop.original_data or '{}')
            except Exception:
                original_data = {}

            already_adjusted = original_data.get('_pricing_adjusted', False)

            if not already_adjusted:
                rate = _tiered_discount(original_rent)
                adjusted = round(original_rent * (1 - rate))
                if adjusted != int(original_rent):
                    try:
                        if not prop.original_data:
                            original_data = {}
                        original_data['_pricing_adjusted'] = True
                        original_data['_original_rent'] = original_rent
                        original_data['_rent_discount_rate'] = rate
                        prop.original_data = json.dumps(original_data)
                    except Exception:
                        pass

                    prop.monthly_rent = adjusted
                    changed = True
                    logger.info(
                        "pricing_service: rent adjusted %.0f → %.0f (%.0f%% off) for %s",
                        original_rent, adjusted, rate * 100, getattr(prop, 'id', '?')
                    )

    fee = prop.application_fee
    if fee is None or (isinstance(fee, (int, float)) and float(fee) < APPLICATION_FEE_FLOOR):
        prop.application_fee = APPLICATION_FEE_FLOOR
        changed = True
        logger.info(
            "pricing_service: application_fee set to $%.0f for %s",
            APPLICATION_FEE_FLOOR, getattr(prop, 'id', '?')
        )

    return changed
