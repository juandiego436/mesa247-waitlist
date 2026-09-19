from __future__ import annotations


class ApplicationError(Exception):
    """Errores de orquestacion. El dominio tiene los suyos en domain/errors.py;
    estos son los que solo existen porque hay una base de datos detras."""


class VenueNotFound(ApplicationError):
    pass


class EntryNotFound(ApplicationError):
    pass


class TableNotFound(ApplicationError):
    pass


class AlreadyInQueue(ApplicationError):
    """Ese movil ya tiene una entrada viva en este local."""

    def __init__(self, token: str) -> None:
        # Devolvemos su token: el comensal que toca 'Unirme' cinco veces
        # nerviosamente no quiere un error, quiere ver su puesto.
        super().__init__("Ya estas en la cola de este local")
        self.token = token
