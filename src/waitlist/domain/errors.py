"""Errores del dominio. No conocen HTTP: traducirlos a codigos de estado es
trabajo del adaptador."""


class DomainError(Exception):
    """Raiz de todo lo que el dominio rechaza."""


class InvalidValue(DomainError):
    """Un value object recibio algo que no puede representar."""


class InvalidTransition(DomainError):
    """La entidad no puede pasar a ese estado desde donde esta.

    Es el error que protege contra el doble toque en la tablet: el segundo
    'Llamar' sobre alguien ya sentado llega aca, no a la base de datos.
    """


class TableNotAvailable(DomainError):
    """La mesa ya esta retenida u ocupada por otro comensal."""


class TableDoesNotFit(DomainError):
    """El grupo no entra en la mesa y el anfitrion no forzo la asignacion."""
