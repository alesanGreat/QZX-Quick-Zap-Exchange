"""Generated startup constants; synchronize from product and lifecycle manifests."""

VERSION = "0.2.2.0.7"
ATTRIBUTION = "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
COMMAND_CATALOG_URL = "https://qzx.yumbale.com/en/commands"
SECURITY_GUIDE_URL = "https://qzx.yumbale.com/en/security"
ONBOARDING = {'schema_version': 1,
 'default_risk': 'read_only',
 'documentation_url_key': 'command_catalog',
 'security_url_key': 'security',
 'steps': [{'stage': 'first_success',
            'command': 'getCurrentDateTime',
            'arguments': ['--output-format', 'iso'],
            'machine_output': True,
            'purpose': {'en': 'Confirm QZX with a fast, read-only ISO '
                              'timestamp.',
                        'es': 'Confirma QZX con una marca de tiempo ISO '
                              'rápida y de solo lectura.'}},
           {'stage': 'explore',
            'command': 'listCommands',
            'arguments': ['file'],
            'machine_output': False,
            'purpose': {'en': 'Filter the installed catalog to commands '
                              'related to files.',
                        'es': 'Filtra el catálogo instalado para ver comandos '
                              'relacionados con archivos.'}},
           {'stage': 'understand',
            'command': 'help',
            'arguments': ['findFiles'],
            'machine_output': False,
            'purpose': {'en': 'Inspect parameters, examples, maturity, and '
                              'safety before execution.',
                        'es': 'Revisa parámetros, ejemplos, madurez y '
                              'seguridad antes de ejecutar.'}}]}
WELCOME_MATURITY = {'stage': 'alpha',
 'label': 'Alpha',
 'sequence': 2,
 'public_executable': True,
 'stability': 'interface_may_change',
 'summary': 'Available for real use and feedback while its interface and '
            'behavior can still evolve.',
 'promotion_review_required': False,
 'assessment_scope': 'development_checkout'}
