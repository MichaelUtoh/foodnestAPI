from app.accounts.schemas import UserRole


def hasAdminPermission(user):
    if user["role"] == UserRole.ADMIN:
        return True
    return False


def hasCreateProductPermission(user):
    if user["role"] in [UserRole.ADMIN, UserRole.WHOLESALER]:
        return True
    return False


def hasOwnerPermission(user):
    if user["role"] in [UserRole.ADMIN, UserRole.WHOLESALER, UserRole.RETAILER]:
        return True
    return False


def hasWholeSalerPermission(user):
    if user["role"] == UserRole.WHOLESALER:
        return True
    return False


def hasRetailerPermission(user):
    if user["role"] == UserRole.RETAILER:
        return True
    return False


def hasDispatcherPermission(user):
    if user["role"] == UserRole.DISPATCH:
        return True
    return False
