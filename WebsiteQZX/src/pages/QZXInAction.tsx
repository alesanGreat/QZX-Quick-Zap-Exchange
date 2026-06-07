import { useEffect, useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Card, CardContent } from "@/components/ui/card";
import { SEO } from "@/components/SEO";
import { Button } from "@/components/ui/button";
import { Terminal, Play, StepForward, RotateCcw } from "lucide-react";

interface DemoCommand {
  command: string;
  output: string[];
  delay: number;
}

interface TranslationsType {
  [language: string]: {
    title: string;
    description: string;
    subtitle: string;
    restart: string;
    play_all: string;
    next_command: string;
    install_info: string;
    try_it: string;
    seo: {
      title: string;
      description: string;
    }
  }
}

const translations: TranslationsType = {
  en: {
    title: "QZX in Action",
    description: "See QZX commands in action with real examples and outputs",
    subtitle: "Watch how QZX commands work across different operating systems",
    restart: "Restart Demo",
    play_all: "Play All",
    next_command: "Next Command",
    install_info: "QZX provides consistent command output formats across different operating systems.",
    try_it: "Try it out by installing with:",
    seo: {
      title: "QZX in Action - See Real Command Examples",
      description: "See QZX (Quick Zap Exchange) in action with real command examples and outputs across different operating systems"
    }
  },
  es: {
    title: "QZX en Acción",
    description: "Mira comandos QZX en acción con ejemplos reales y sus salidas",
    subtitle: "Observa cómo funcionan los comandos QZX en diferentes sistemas operativos",
    restart: "Reiniciar Demo",
    play_all: "Reproducir Todo",
    next_command: "Siguiente Comando",
    install_info: "QZX proporciona formatos de salida de comandos consistentes en diferentes sistemas operativos.",
    try_it: "Pruébalo instalando con:",
    seo: {
      title: "QZX en Acción - Ver Ejemplos Reales de Comandos",
      description: "Mira QZX (Quick Zap Exchange) en acción con ejemplos reales de comandos y salidas en diferentes sistemas operativos"
    }
  },
  pt: {
    title: "QZX em Ação",
    description: "Veja comandos QZX em ação com exemplos reais e saídas",
    subtitle: "Observe como os comandos QZX funcionam em diferentes sistemas operacionais",
    restart: "Reiniciar Demo",
    play_all: "Reproduzir Tudo",
    next_command: "Próximo Comando",
    install_info: "QZX fornece formatos de saída de comando consistentes em diferentes sistemas operacionais.",
    try_it: "Experimente instalando com:",
    seo: {
      title: "QZX em Ação - Veja Exemplos Reais de Comandos",
      description: "Veja QZX (Quick Zap Exchange) em ação com exemplos reais de comandos e saídas em diferentes sistemas operacionais"
    }
  },
  it: {
    title: "QZX in Azione",
    description: "Vedi i comandi QZX in azione con esempi reali e output",
    subtitle: "Guarda come funzionano i comandi QZX su diversi sistemi operativi",
    restart: "Riavvia Demo",
    play_all: "Riproduci Tutto",
    next_command: "Comando Successivo",
    install_info: "QZX fornisce formati di output dei comandi coerenti su diversi sistemi operativi.",
    try_it: "Provalo installando con:",
    seo: {
      title: "QZX in Azione - Vedi Esempi Reali di Comandi",
      description: "Vedi QZX (Quick Zap Exchange) in azione con esempi reali di comandi e output su diversi sistemi operativi"
    }
  },
  fr: {
    title: "QZX en Action",
    description: "Voir les commandes QZX en action avec des exemples réels et des sorties",
    subtitle: "Regardez comment les commandes QZX fonctionnent sur différents systèmes d'exploitation",
    restart: "Redémarrer la Démo",
    play_all: "Tout Lire",
    next_command: "Commande Suivante",
    install_info: "QZX fournit des formats de sortie de commande cohérents sur différents systèmes d'exploitation.",
    try_it: "Essayez-le en installant avec:",
    seo: {
      title: "QZX en Action - Voir des Exemples Réels de Commandes",
      description: "Voir QZX (Quick Zap Exchange) en action avec des exemples réels de commandes et des sorties sur différents systèmes d'exploitation"
    }
  },
  de: {
    title: "QZX in Aktion",
    description: "Sehen Sie QZX-Befehle in Aktion mit echten Beispielen und Ausgaben",
    subtitle: "Beobachten Sie, wie QZX-Befehle auf verschiedenen Betriebssystemen funktionieren",
    restart: "Demo Neustarten",
    play_all: "Alles Abspielen",
    next_command: "Nächster Befehl",
    install_info: "QZX bietet konsistente Befehlsausgabeformate über verschiedene Betriebssysteme hinweg.",
    try_it: "Probieren Sie es aus, indem Sie installieren mit:",
    seo: {
      title: "QZX in Aktion - Sehen Sie echte Befehlsbeispiele",
      description: "Sehen Sie QZX (Quick Zap Exchange) in Aktion mit echten Befehlsbeispielen und Ausgaben auf verschiedenen Betriebssystemen"
    }
  },
  zh: {
    title: "QZX 实战",
    description: "通过真实示例和输出查看 QZX 命令的运行情况",
    subtitle: "观察 QZX 命令如何在不同操作系统上工作",
    restart: "重新开始演示",
    play_all: "播放全部",
    next_command: "下一个命令",
    install_info: "QZX 在不同操作系统上提供一致的命令输出格式。",
    try_it: "通过以下方式安装试用：",
    seo: {
      title: "QZX 实战 - 查看真实命令示例",
      description: "通过真实命令示例和在不同操作系统上的输出，查看 QZX（Quick Zap Exchange）的实际运行情况"
    }
  },
  ar: {
    title: "QZX في العمل",
    description: "شاهد أوامر QZX في العمل مع أمثلة حقيقية والنتائج",
    subtitle: "شاهد كيف تعمل أوامر QZX عبر أنظمة التشغيل المختلفة",
    restart: "إعادة تشغيل العرض",
    play_all: "تشغيل الكل",
    next_command: "الأمر التالي",
    install_info: "يوفر QZX تنسيقات إخراج أوامر متسقة عبر أنظمة التشغيل المختلفة.",
    try_it: "جربه عن طريق التثبيت باستخدام:",
    seo: {
      title: "QZX في العمل - شاهد أمثلة أوامر حقيقية",
      description: "شاهد QZX (Quick Zap Exchange) في العمل مع أمثلة أوامر حقيقية والنتائج عبر أنظمة تشغيل مختلفة"
    }
  }
};

// Demo commands with their outputs
const demoCommands: DemoCommand[] = [
  {
    command: "qzx --help",
    output: [
      "QZX (Quick Zap Exchange) v0.2.2",
      "",
      "USAGE:",
      "  qzx [COMMAND] [OPTIONS]",
      "",
      "COMMANDS:",
      "  SystemCommands:",
      "    SystemInfo           - Shows operating system information",
      "    checkSystemPath      - Diagnoses PATH variable and locates executables",
      "    getToday             - Displays detailed date and time information",
      "    inspectPort          - Identifies processes utilizing a specific port",
      "    isAdmin              - Checks if the user has administrator privileges",
      "  FileCommands:",
      "    ListFiles            - Lists files in a directory with wildcards",
      "    FindFiles            - Searches for files with patterns and options",
      "    detectFileType       - Identifies file type by its signature",
      "    cleanDevCaches       - Cleans heavy development cache folders",
      "  DevelopmentCommands:",
      "    getGitStatus         - Retrieves Git repository status and history",
      "    scanProject          - Identifies technologies, scripts, env sync health",
      "    analyzeComplexity    - Analyzes code complexity metrics recursively",
      "    auditLanguages       - Audits language representation & warns on underrepresented ones",
      "  NetworkCommands:",
      "    checkSslCertificate  - Inspects SSL/TLS validity and cipher details",
      "    testWebSpeed         - Evaluates remote host connection latency",
      "",
      "OPTIONS:",
      "  -h, --help     Show this help message",
      "  -v, --version  Show program version",
      ""
    ],
    delay: 2000
  },
  {
    command: "qzx SystemInfo",
    output: [
      "SYSTEM INFORMATION",
      "===============================================================",
      "OS:               Windows 11 Pro",
      "Version:          10.0.22621",
      "Architecture:     AMD64 (64-bit)",
      "Processor:        11th Gen Intel Core i7-11800H @ 2.30GHz",
      "Python:           3.11.4 (CPython)",
      "",
      "Memory:           16.0 GB total",
      "Username:         alesan",
      "Hostname:         LAPTOP-QZX",
      "Current Directory: C:\\Users\\alesan\\Documents\\Projects",
      "",
      "Environment Variables:",
      "  PATH:            C:\\Program Files\\Python311\\;C:\\Windows\\system32;...",
      "  PYTHONPATH:      C:\\Users\\alesan\\AppData\\Local\\Programs\\Python",
      "  HOME:            C:\\Users\\alesan",
      "===============================================================",
      "",
      "* Same command works across Windows, macOS and Linux with consistent format"
    ],
    delay: 2000
  },
  {
    command: "qzx scanProject",
    output: [
      "Project scan completed for 'C:\\Users\\alesan\\Projects\\quick-zap-shop':",
      "- Detected Tech: React, TypeScript, Node.js, TailwindCSS",
      "- Package Managers: npm, pnpm",
      "- Node Project: quick-zap-shop (v1.0.4)",
      "  - NPM Scripts: dev, build, lint, preview, test, deploy",
      "- Environment warning: 3 keys are missing in '.env' that are defined in '.env.example':",
      "  - STRIPE_WEBHOOK_SECRET",
      "  - REDIS_URL",
      "  - EMAIL_SERVER_PORT",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"project_path\": \"C:\\\\Users\\\\alesan\\\\Projects\\\\quick-zap-shop\",",
      "  \"project_types\": [\"React\", \"TypeScript\", \"Node.js\", \"TailwindCSS\"],",
      "  \"package_managers\": [\"npm\", \"pnpm\"],",
      "  \"node_details\": {",
      "    \"name\": \"quick-zap-shop\",",
      "    \"version\": \"1.0.4\",",
      "    \"scripts\": { \"dev\": \"vite\", \"build\": \"tsc && vite build\" }",
      "  },",
      "  \"env_diagnostics\": {",
      "    \"example_file_found\": true,",
      "    \"local_file_found\": true,",
      "    \"missing_keys\": [\"STRIPE_WEBHOOK_SECRET\", \"REDIS_URL\", \"EMAIL_SERVER_PORT\"]",
      "  }",
      "}"
    ],
    delay: 2500
  },
  {
    command: "qzx checkSystemPath python",
    output: [
      "PATH Diagnostics Summary:",
      "- Total entries in PATH: 24",
      "- Valid directories: 19",
      "- Broken paths: 4",
      "- Duplicate entries: 1",
      "",
      "[WARNING] Broken entries identified:",
      "  - Index 5: 'C:\\Program Files\\Common Files\\Oracle\\Java\\javapath_dead' (Directory does not exist.)",
      "  - Index 12: 'C:\\Users\\alesan\\AppData\\Local\\Programs\\Python\\Python39-dead' (Directory does not exist.)",
      "",
      "Binary resolution search for 'python':",
      "- Found 3 location(s) on PATH:",
      "  >>> [First choice] C:\\Users\\alesan\\.venv\\Scripts\\python.exe",
      "      [Shadowed]     C:\\Users\\alesan\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "      [Shadowed]     C:\\Windows\\python.exe",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"binary_searched\": \"python\",",
      "  \"path_summary\": {",
      "    \"total_entries\": 24,",
      "    \"valid_count\": 19,",
      "    \"broken_count\": 4,",
      "    \"duplicate_count\": 1",
      "  },",
      "  \"broken_paths\": [",
      "    { \"index\": 5, \"raw_path\": \"C:\\\\Program Files\\\\Common Files\\\\Oracle\\\\Java\\\\javapath_dead\", \"reason\": \"Directory does not exist.\" }",
      "  ],",
      "  \"binary_matches\": [",
      "    { \"path_index\": 2, \"directory\": \"C:\\\\Users\\\\alesan\\\\.venv\\\\Scripts\", \"filename\": \"python.exe\", \"full_path\": \"C:\\\\Users\\\\alesan\\\\.venv\\\\Scripts\\\\python.exe\" },",
      "    { \"path_index\": 8, \"directory\": \"C:\\\\Users\\\\alesan\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\Python311\", \"filename\": \"python.exe\", \"full_path\": \"C:\\\\Users\\\\alesan\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\Python311\\\\python.exe\" }",
      "  ]",
      "}"
    ],
    delay: 2500
  },
  {
    command: "qzx checkSslCertificate github.com",
    output: [
      "Connecting securely to github.com:443...",
      "",
      "SSL Certificate Diagnostic for 'github.com':",
      "- Status: VALID",
      "- Common Name (CN): github.com",
      "- Issuer: DigiCert TLS Hybrid ECC SHA384 2020 CA1",
      "- SSL Version: TLSv1.3",
      "- Cipher Suite: TLS_AES_256_GCM_SHA384 (256 bits)",
      "- Expiry Date: 2027-03-15 23:59:59 UTC (282 days left)",
      "- Alt Names (SAN): github.com, www.github.com, *.github.com",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"host\": \"github.com\",",
      "  \"port\": 443,",
      "  \"is_valid\": true,",
      "  \"is_expired\": false,",
      "  \"hostname_match\": true,",
      "  \"days_remaining\": 282,",
      "  \"subject\": { \"commonName\": \"github.com\" },",
      "  \"issuer\": { \"commonName\": \"DigiCert TLS Hybrid ECC SHA384 2020 CA1\" },",
      "  \"subject_alt_names\": [\"github.com\", \"www.github.com\", \"*.github.com\"],",
      "  \"ssl_version\": \"TLSv1.3\",",
      "  \"cipher_suite\": \"TLS_AES_256_GCM_SHA384\",",
      "  \"cipher_bits\": 256",
      "}"
    ],
    delay: 2500
  },
  {
    command: "qzx analyzeComplexity src/ -r",
    output: [
      "Complexity analysis completed for 'C:\\Users\\alesan\\Projects\\quick-zap-shop\\src':",
      "- Files analyzed: 42",
      "- Total Lines of Code (LOC): 8,421 (74% Code, 18% Comments, 8% Blank)",
      "- Average Cyclomatic Complexity: 4.8 (Low risk)",
      "- Average Maintainability Index: 82.4 / 100 (Very Good)",
      "",
      "⚠️  Attention Required (High Complexity Files):",
      "  - src/components/CheckoutForm.tsx:",
      "    - LOC: 412 | Cyclomatic: 24 (High risk) | Maintainability: 42.1 (Hard to maintain)",
      "    - Suggestion: Refactor checkoutState reducer & split payment handlers.",
      "  - src/utils/api-client.ts:",
      "    - LOC: 289 | Cyclomatic: 18 (Medium risk) | Maintainability: 56.4 (Moderate)",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"files_analyzed\": 42,",
      "  \"summary\": {",
      "    \"total_loc\": 8421,",
      "    \"code_loc\": 6231,",
      "    \"comment_loc\": 1515,",
      "    \"blank_loc\": 675,",
      "    \"avg_cyclomatic_complexity\": 4.8,",
      "    \"avg_maintainability_index\": 82.4",
      "  },",
      "  \"warnings\": [",
      "    { \"file\": \"src/components/CheckoutForm.tsx\", \"loc\": 412, \"complexity\": 24, \"maintainability\": 42.1 }",
      "  ]",
      "}"
    ],
    delay: 3000
  },
  {
    command: "qzx inspectPort 3000",
    output: [
      "Port 3000 is in use by: node.exe (PIDs: 1234).",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"port\": 3000,",
      "  \"in_use\": true,",
      "  \"killed\": false,",
      "  \"processes\": [",
      "    {",
      "      \"pid\": 1234,",
      "      \"name\": \"node.exe\",",
      "      \"status\": \"running\",",
      "      \"username\": \"alesan\",",
      "      \"memory_usage\": { \"rss_readable\": \"45.12 MB\" }",
      "    }",
      "  ]",
      "}"
    ],
    delay: 2500
  },
  {
    command: "qzx cleanDevCaches . true",
    output: [
      "Dry-run scan completed for 'C:\\Users\\alesan\\Projects\\QZX':",
      "- Identified cache folders: 3",
      "- Total space: 1.42 GB",
      "- Note: This was a dry run. No folders were deleted.",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"dry_run\": true,",
      "  \"total_folders_found\": 3,",
      "  \"total_space_saved_readable\": \"1.42 GB\",",
      "  \"found_folders\": [",
      "    { \"name\": \"node_modules\", \"size_readable\": \"1.38 GB\" },",
      "    { \"name\": \"__pycache__\", \"size_readable\": \"4.2 KB\" },",
      "    { \"name\": \"dist\", \"size_readable\": \"38.4 MB\" }",
      "  ]",
      "}"
    ],
    delay: 3000
  },
  {
    command: "qzx traceEnvVar STRIPE_API_KEY",
    output: [
      "Tracing Environment Variable 'STRIPE_API_KEY' in 'C:\\Users\\alesan\\Projects\\quick-zap-shop':",
      "",
      "- Env Files Audited:",
      "  - .env: DEFINED (masked_value: sk_live...12ef)",
      "  - .env.example: DEFINED (masked_value: <empty>)",
      "  - .env.local: NOT DEFINED",
      "",
      "- Active Code References:",
      "  - [python] src/payments/stripe_provider.py (lines 12-14):",
      "    >>> api_key = os.getenv('STRIPE_API_KEY')",
      "  - [js/ts] src/components/CheckoutButton.tsx (lines 45-47):",
      "    >>> const key = process.env.STRIPE_API_KEY || 'pk_test_placeholder' (Fallback: 'pk_test_placeholder')",
      "",
      "- Diagnostics & Warnings:",
      "  - WARNING: The value configured in '.env' has length 32 but matches format of active keys.",
      "  - INFO: Sync status between '.env' and '.env.example' is OK (both define the key).",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"variable_name\": \"STRIPE_API_KEY\",",
      "  \"project_path\": \"C:\\\\Users\\\\alesan\\\\Projects\\\\quick-zap-shop\",",
      "  \"env_files_diagnostics\": {",
      "    \".env\": {",
      "      \"defined\": true,",
      "      \"value_found\": true,",
      "      \"masked_value\": \"sk_live...12ef\"",
      "    },",
      "    \".env.example\": {",
      "      \"defined\": true,",
      "      \"value_found\": false,",
      "      \"masked_value\": \"<empty>\"",
      "    }",
      "  },",
      "  \"references_count\": 2,",
      "  \"references\": [",
      "    {",
      "      \"filepath\": \"src/payments/stripe_provider.py\",",
      "      \"line_number\": 12,",
      "      \"line_content\": \"api_key = os.getenv('STRIPE_API_KEY')\",",
      "      \"language\": \"python\",",
      "      \"fallback_value\": null",
      "    },",
      "    {",
      "      \"filepath\": \"src/components/CheckoutButton.tsx\",",
      "      \"line_number\": 45,",
      "      \"line_content\": \"const key = process.env.STRIPE_API_KEY || 'pk_test_placeholder'\",",
      "      \"language\": \"javascript\",",
      "      \"fallback_value\": \"'pk_test_placeholder'\"",
      "    }",
      "  ]",
      "}"
    ],
    delay: 3000
  },
  {
    command: "qzx traceCircularImports",
    output: [
      "Circular Import Trace completed for 'C:\\Users\\alesan\\Projects\\quick-zap-shop\\src':",
      "",
      "- Scanned Modules: 85",
      "- Import Dependency Graph: 412 edges",
      "- Circular Import Cycles Detected: 2 cycles found!",
      "",
      "Cycle #1 (Length 3):",
      "  [1] src/users/models.py",
      "      --> imports src/orders/models.py (line 14)",
      "  [2] src/orders/models.py",
      "      --> imports src/payments/gateways.py (line 8)",
      "  [3] src/payments/gateways.py",
      "      --> imports src/users/models.py (line 22)",
      "",
      "Cycle #2 (Length 2):",
      "  [1] src/analytics/dashboard.py",
      "      --> imports src/analytics/metrics.py (line 4)",
      "  [2] src/analytics/metrics.py",
      "      --> imports src/analytics/dashboard.py (line 18)",
      "",
      "⚠️ Circular imports delay application startup and cause runtime crashes.",
      "💡 Suggestion: Move shared database session models to a core context module.",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"scanned_modules_count\": 85,",
      "  \"cycles_detected_count\": 2,",
      "  \"cycles\": [",
      "    [",
      "      { \"filepath\": \"src/users/models.py\", \"imported_filepath\": \"src/orders/models.py\", \"line_number\": 14 },",
      "      { \"filepath\": \"src/orders/models.py\", \"imported_filepath\": \"src/payments/gateways.py\", \"line_number\": 8 },",
      "      { \"filepath\": \"src/payments/gateways.py\", \"imported_filepath\": \"src/users/models.py\", \"line_number\": 22 }",
      "    ],",
      "    [",
      "      { \"filepath\": \"src/analytics/dashboard.py\", \"imported_filepath\": \"src/analytics/metrics.py\", \"line_number\": 4 },",
      "      { \"filepath\": \"src/analytics/metrics.py\", \"imported_filepath\": \"src/analytics/dashboard.py\", \"line_number\": 18 }",
      "    ]",
      "  ]",
      "}"
    ],
    delay: 3000
  },
  {
    command: "qzx findDeadCode",
    output: [
      "Dead Code Scan completed for 'C:\\Users\\alesan\\Projects\\quick-zap-shop':",
      "",
      "- Scanned Files: 104 (Python, JavaScript, TypeScript)",
      "- Declared Symbols (Classes/Functions/Exports): 342",
      "- Unreferenced Symbols Found: 3 dead symbols",
      "",
      "[DEAD CODE] Unreferenced Declarations:",
      "  - src/utils/formatters.ts:",
      "    >>> export function formatLegacyCurrency(val: number) { ... } (Line 72)",
      "    - Suggestion: Safe to remove. Symbol is exported but never imported/used.",
      "  - src/auth/legacy_auth.py:",
      "    >>> class LegacyTokenVerifier: (Line 18)",
      "    - Suggestion: Safe to remove. Class is defined but never referenced.",
      "  - src/orders/models.py:",
      "    >>> def get_archived_orders_count(): (Line 143)",
      "    - Suggestion: Safe to remove. Function is defined but never referenced.",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"scanned_files_count\": 104,",
      "  \"declared_symbols_count\": 342,",
      "  \"dead_symbols_count\": 3,",
      "  \"dead_symbols\": [",
      "    {",
      "      \"filepath\": \"src/utils/formatters.ts\",",
      "      \"symbol_name\": \"formatLegacyCurrency\",",
      "      \"symbol_type\": \"function\",",
      "      \"line_number\": 72",
      "    },",
      "    {",
      "      \"filepath\": \"src/auth/legacy_auth.py\",",
      "      \"symbol_name\": \"LegacyTokenVerifier\",",
      "      \"symbol_type\": \"class\",",
      "      \"line_number\": 18",
      "    },",
      "    {",
      "      \"filepath\": \"src/orders/models.py\",",
      "      \"symbol_name\": \"get_archived_orders_count\",",
      "      \"symbol_type\": \"function\",",
      "      \"line_number\": 143",
      "    }",
      "  ]",
      "}"
    ],
    delay: 3000
  },
  {
    command: "qzx auditLanguages",
    output: [
      "QZX Language Representation Audit Report:",
      "- Scanned Path: C:\\Users\\alesan\\Projects\\quick-zap-shop",
      "- Total code files matched: 120",
      "- Minimum file threshold: 3",
      "",
      "Detected Languages Profile:",
      "  - TypeScript: 58 files (48.3%)",
      "  - PHP: 42 files (35.0%)",
      "  - Python: 20 files (16.7%)",
      "",
      "⚠️  ALERTS FOR SUBREPRESENTED LANGUAGES:",
      "  1. [WARNING] TypeScript (58 files, 48.3%):",
      "     Reason: Language has moderate presence (58 files, 48.3%) but is missing some QZX tools.",
      "     Missing in QZX: scaffolding",
      "  2. [WARNING] PHP (42 files, 35.0%):",
      "     Reason: Language has moderate presence (42 files, 35.0%) but is missing some QZX tools.",
      "     Missing in QZX: scaffolding",
      "",
      "JSON result:",
      "{",
      "  \"success\": true,",
      "  \"scan_path\": \"C:\\\\Users\\\\alesan\\\\Projects\\\\quick-zap-shop\",",
      "  \"total_files\": 120,",
      "  \"languages_found\": {",
      "    \"typescript\": 58,",
      "    \"php\": 42,",
      "    \"python\": 20",
      "  },",
      "  \"alerts_count\": 2,",
      "  \"alerts\": [",
      "    {",
      "      \"language\": \"typescript\",",
      "      \"display_name\": \"TypeScript\",",
      "      \"file_count\": 58,",
      "      \"percentage\": 48.3,",
      "      \"severity\": \"WARNING\",",
      "      \"reason\": \"Language has moderate presence (58 files, 48.3%) but is missing some QZX tools.\",",
      "      \"missing_capabilities\": [\"scaffolding\"]",
      "    },",
      "    {",
      "      \"language\": \"php\",",
      "      \"display_name\": \"PHP\",",
      "      \"file_count\": 42,",
      "      \"percentage\": 35.0,",
      "      \"severity\": \"WARNING\",",
      "      \"reason\": \"Language has moderate presence (42 files, 35.0%) but is missing some QZX tools.\",",
      "      \"missing_capabilities\": [\"scaffolding\"]",
      "    }",
      "  ],",
      "  \"fully_represented\": [",
      "    { \"language\": \"python\", \"display_name\": \"Python\", \"file_count\": 20, \"percentage\": 16.7 }",
      "  ],",
      "  \"partially_represented\": [",
      "    {",
      "      \"language\": \"typescript\",",
      "      \"display_name\": \"TypeScript\",",
      "      \"file_count\": 58,",
      "      \"percentage\": 48.3,",
      "      \"supported_capabilities\": [\"complexity\", \"dead_code\", \"env_fallbacks\"],",
      "      \"missing_capabilities\": [\"scaffolding\"]",
      "    },",
      "    {",
      "      \"language\": \"php\",",
      "      \"display_name\": \"PHP\",",
      "      \"file_count\": 42,",
      "      \"percentage\": 35.0,",
      "      \"supported_capabilities\": [\"complexity\", \"dead_code\", \"env_fallbacks\"],",
      "      \"missing_capabilities\": [\"scaffolding\"]",
      "    }",
      "  ]",
      "}"
    ],
    delay: 3000
  }
];

const QZXInAction = () => {
  const { language } = useLanguage();
  const t = translations[language as keyof typeof translations] || translations.en;
  
  const [currentCommandIndex, setCurrentCommandIndex] = useState(0);
  const [commandText, setCommandText] = useState("");
  const [outputText, setOutputText] = useState<string[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [playAll, setPlayAll] = useState(true);
  const [showPrompt, setShowPrompt] = useState(true);
  const [userInteracted, setUserInteracted] = useState(false);
  
  // Function to type command character by character
  const typeCommand = (command: string, index: number = 0) => {
    if (index === 0) {
      setIsTyping(true);
      setCommandText("");
      setOutputText([]);
    }
    
    if (index < command.length) {
      setCommandText(prev => prev + command[index]);
      setTimeout(() => typeCommand(command, index + 1), 30 + Math.random() * 50);
    } else {
      setIsTyping(false);
      setTimeout(() => {
        setOutputText(demoCommands[currentCommandIndex].output);
        
        if (playAll) {
          const nextCommandTimer = setTimeout(() => {
            if (currentCommandIndex < demoCommands.length - 1) {
              setCurrentCommandIndex(prev => prev + 1);
            } else {
              // Loop back to the first command
              setCurrentCommandIndex(0);
            }
          }, 5000); // 5 second pause before next command
          
          return () => clearTimeout(nextCommandTimer);
        }
      }, 500);
    }
  };
  
  // Start demo effect
  useEffect(() => {
    if (!isTyping && (playAll || showPrompt)) {
      typeCommand(demoCommands[currentCommandIndex].command);
      setShowPrompt(false);
    }
  }, [currentCommandIndex, playAll, showPrompt]);
  
  // Handle play all toggle
  useEffect(() => {
    if (playAll && !isTyping) {
      setCurrentCommandIndex(0);
      setShowPrompt(true);
    }
  }, [playAll]);
  
  // Set up user interaction handlers
  const handleUserInteraction = () => {
    if (!userInteracted) {
      setUserInteracted(true);
    }
  };
  
  const handleNextCommand = () => {
    handleUserInteraction();
    if (currentCommandIndex < demoCommands.length - 1) {
      setCurrentCommandIndex(prev => prev + 1);
    } else {
      // Loop back to first command
      setCurrentCommandIndex(0);
    }
    setShowPrompt(true);
  };
  
  const handleRestart = () => {
    handleUserInteraction();
    setPlayAll(false);
    setCurrentCommandIndex(0);
    setCommandText("");
    setOutputText([]);
    setShowPrompt(true);
  };
  
  const handlePlayToggle = () => {
    handleUserInteraction();
    setPlayAll(!playAll);
  };
  
  return (
    <>
      <SEO 
        title={t.seo.title}
        description={t.seo.description}
        keywords="QZX, commands, examples, terminal, cross-platform"
        url="/qzx-in-action"
      />
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center mb-6">
          <Terminal className="h-8 w-8 mr-2 text-primary" />
          <h1 className="text-4xl font-bold text-primary">{t.title}</h1>
        </div>
        
        <p className="text-muted-foreground mb-10 max-w-3xl">
          {t.description}
        </p>
        
        <h2 className="text-xl mb-6">
          {t.subtitle}
        </h2>
        
        <div className="mb-6 flex flex-wrap gap-4">
          <Button 
            variant="outline" 
            onClick={handleRestart}
            className="flex items-center"
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            {t.restart}
          </Button>
          
          <Button 
            variant={playAll ? "default" : "outline"}
            onClick={handlePlayToggle}
            className="flex items-center"
            disabled={isTyping}
          >
            <Play className="mr-2 h-4 w-4" />
            {t.play_all}
          </Button>
          
          <Button 
            variant="outline" 
            onClick={handleNextCommand}
            className="flex items-center"
            disabled={isTyping || playAll}
          >
            <StepForward className="mr-2 h-4 w-4" />
            {t.next_command}
          </Button>
        </div>
        
        <Card className="max-w-4xl mb-10 border-2">
          <CardContent className="p-0">
            <div className="bg-zinc-900 text-zinc-50 rounded-t-lg p-2 flex items-center">
              <div className="flex space-x-2 mr-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
              </div>
              <div className="flex-grow text-sm font-mono">Terminal</div>
            </div>
            
            <div className="bg-black text-green-500 p-4 font-mono text-sm rounded-b-lg min-h-[400px] overflow-auto whitespace-pre-wrap text-left" style={{ textAlign: 'left' }}>
              <div className="mb-2 text-left">
                <span className="text-blue-400">user@qzx</span>:<span className="text-purple-400">~</span>$ {commandText}
                {isTyping && <span className="animate-pulse">▋</span>}
              </div>
              
              {outputText.map((line, index) => (
                <div key={index} className="mb-1 text-left" style={{ textAlign: 'left' }}>{line}</div>
              ))}
              
              {!isTyping && outputText.length > 0 && (
                <div className="mt-2 text-left">
                  <span className="text-blue-400">user@qzx</span>:<span className="text-purple-400">~</span>$ <span className="animate-pulse">▋</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        
        <div className="text-sm text-muted-foreground max-w-2xl">
          <p>
            {t.install_info}
            <br />
            {t.try_it} <code className="bg-muted px-1 py-0.5 rounded">pip install qzx</code>
          </p>
        </div>
      </div>
    </>
  );
};

export default QZXInAction; 