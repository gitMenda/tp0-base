from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Bet:
    """
    Domain model representing a lottery bet.
    """
    nombre: str
    apellido: str
    documento: str
    nacimiento: str
    numero: int
    
    def __post_init__(self):
        """Validate bet data after initialization."""
        if not self.nombre or not self.apellido:
            raise ValueError("Nombre and apellido are required")
        
        if not self.documento:
            raise ValueError("Documento is required")
        
        if not self.nacimiento:
            raise ValueError("Nacimiento is required")
        
        if not isinstance(self.numero, int) or self.numero < 0:
            raise ValueError("Numero must be a positive integer")
    
    def to_dict(self) -> dict:
        """Convert bet to dictionary for serialization."""
        return {
            'nombre': self.nombre,
            'apellido': self.apellido,
            'documento': self.documento,
            'nacimiento': self.nacimiento,
            'numero': self.numero
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Bet':
        """Create bet from dictionary."""
        return cls(
            nombre=data['nombre'],
            apellido=data['apellido'],
            documento=data['documento'],
            nacimiento=data['nacimiento'],
            numero=data['numero']
        )

@dataclass
class BetResponse:
    """
    Response model for bet confirmation.
    """
    success: bool
    message: str
    dni: Optional[str] = None
    numero: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert response to dictionary for serialization."""
        return {
            'success': self.success,
            'message': self.message,
            'dni': self.dni,
            'numero': self.numero
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BetResponse':
        """Create response from dictionary."""
        return cls(
            success=data['success'],
            message=data['message'],
            dni=data.get('dni'),
            numero=data.get('numero')
        )
