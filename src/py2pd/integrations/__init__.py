"""Third-party integrations for py2pd.

Submodules
----------
cypd
    Patch validation via libpd / cypd.
hvcc
    hvcc (Heavy Compiler Collection) integration.
"""

from .cypd import ValidationResult as ValidationResult
from .cypd import validate_patch as validate_patch
from .hvcc import HVCC_SUPPORTED_OBJECTS as HVCC_SUPPORTED_OBJECTS
from .hvcc import HeavyPatcher as HeavyPatcher
from .hvcc import HvccCompileError as HvccCompileError
from .hvcc import HvccCompileResult as HvccCompileResult
from .hvcc import HvccError as HvccError
from .hvcc import HvccGenerator as HvccGenerator
from .hvcc import HvccUnsupportedError as HvccUnsupportedError
from .hvcc import HvccValidationResult as HvccValidationResult
from .hvcc import compile_hvcc as compile_hvcc
from .hvcc import validate_for_hvcc as validate_for_hvcc
