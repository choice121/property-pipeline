import logging

logger = logging.getLogger(__name__)

APPLICATION_FEE_FLOOR = 50.0


def apply_pricing_rules(prop) -> bool:
    changed = False

    fee = prop.application_fee
    if fee is None or (isinstance(fee, (int, float)) and float(fee) < APPLICATION_FEE_FLOOR):
        prop.application_fee = APPLICATION_FEE_FLOOR
        changed = True
        logger.info(
            "pricing_service: application_fee set to $%.0f for %s",
            APPLICATION_FEE_FLOOR, getattr(prop, 'id', '?')
        )

    return changed
