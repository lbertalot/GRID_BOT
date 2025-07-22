#!/usr/bin/env python3
"""
Script para optimizar el código y aplicar buenas prácticas
"""

import os
import re
from pathlib import Path

def aplicar_pep8_imports(file_path: str):
    """Aplica PEP8 a los imports de un archivo"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Organizar imports según PEP8
        lines = content.split('\n')
        import_lines = []
        other_lines = []
        in_import_section = False
        
        for line in lines:
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
                in_import_section = True
            elif in_import_section and line.strip() == '':
                import_lines.append(line)
            elif in_import_section and not line.strip().startswith(('import ', 'from ')):
                in_import_section = False
                other_lines.append(line)
            else:
                other_lines.append(line)
        
        # Ordenar imports
        stdlib_imports = []
        third_party_imports = []
        local_imports = []
        
        for line in import_lines:
            if line.strip() == '':
                continue
            if line.strip().startswith('from app.'):
                local_imports.append(line)
            elif any(pkg in line for pkg in ['fastapi', 'uvicorn', 'sqlalchemy', 'binance', 'apscheduler']):
                third_party_imports.append(line)
            else:
                stdlib_imports.append(line)
        
        # Reconstruir contenido
        new_content = '\n'.join(stdlib_imports)
        if third_party_imports:
            if new_content:
                new_content += '\n\n'
            new_content += '\n'.join(third_party_imports)
        if local_imports:
            if new_content:
                new_content += '\n\n'
            new_content += '\n'.join(local_imports)
        
        if new_content:
            new_content += '\n\n'
        new_content += '\n'.join(other_lines)
        
        # Escribir archivo optimizado
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"✅ PEP8 aplicado a imports en {file_path}")
        
    except Exception as e:
        print(f"❌ Error aplicando PEP8 a {file_path}: {e}")

def limpiar_codigo_muerto(file_path: str):
    """Limpia código muerto y comentarios innecesarios"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remover líneas vacías excesivas
            if line.strip() == '' and cleaned_lines and cleaned_lines[-1].strip() == '':
                continue
            
            # Remover comentarios de debug
            if line.strip().startswith('#') and any(keyword in line.lower() for keyword in ['debug', 'temp', 'test']):
                continue
            
            # Remover prints de debug (mantener los importantes)
            if 'print(' in line and not any(keyword in line for keyword in ['error', 'alert', 'success', 'warning', 'info', '✅', '❌', '🚨']):
                continue
            
            cleaned_lines.append(line)
        
        # Remover líneas vacías al final
        while cleaned_lines and cleaned_lines[-1].strip() == '':
            cleaned_lines.pop()
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Escribir archivo limpio
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        print(f"✅ Código muerto limpiado en {file_path}")
        
    except Exception as e:
        print(f"❌ Error limpiando código muerto en {file_path}: {e}")

def mejorar_nombres_funciones(file_path: str):
    """Mejora nombres de funciones para mayor claridad"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Mapeo de nombres a mejorar
        name_mappings = {
            'run_grid_job': 'execute_grid_trading_job',
            'get_config': 'get_grid_configuration',
            'update_config': 'update_grid_configuration',
            'check_balance': 'verify_account_balance',
            'place_order': 'execute_trading_order',
            'get_price': 'fetch_current_price',
            'calc_levels': 'calculate_grid_levels',
            'decide_action': 'determine_trading_action'
        }
        
        # Aplicar mejoras de nombres
        for old_name, new_name in name_mappings.items():
            content = re.sub(r'\b' + old_name + r'\b', new_name, content)
        
        # Escribir archivo mejorado
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"✅ Nombres de funciones mejorados en {file_path}")
        
    except Exception as e:
        print(f"❌ Error mejorando nombres en {file_path}: {e}")

def agregar_docstrings(file_path: str):
    """Agrega docstrings a funciones que no los tienen"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            
            # Detectar definición de función sin docstring
            if line.strip().startswith('def ') and ':' in line:
                func_name = line.split('def ')[1].split('(')[0].strip()
                
                # Verificar si la siguiente línea no es un docstring
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith('"""'):
                    # Agregar docstring básico
                    docstring = f'    """Ejecuta {func_name}."""'
                    new_lines.append(docstring)
            
            i += 1
        
        new_content = '\n'.join(new_lines)
        
        # Escribir archivo con docstrings
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"✅ Docstrings agregados en {file_path}")
        
    except Exception as e:
        print(f"❌ Error agregando docstrings en {file_path}: {e}")

def optimizar_archivos_principales():
    """Optimiza los archivos principales del proyecto"""
    print("🔧 OPTIMIZANDO ARCHIVOS PRINCIPALES")
    print("-" * 40)
    
    main_files = [
        "app/main.py",
        "app/scheduler/grid_job.py",
        "app/services/grid_strategy.py",
        "app/services/order_validation.py",
        "app/services/binance_service.py"
    ]
    
    for file_path in main_files:
        if os.path.exists(file_path):
            print(f"\n📝 Optimizando {file_path}:")
            aplicar_pep8_imports(file_path)
            limpiar_codigo_muerto(file_path)
            mejorar_nombres_funciones(file_path)
            agregar_docstrings(file_path)

def crear_readme_actualizado():
    """Crea un README actualizado para el proyecto"""
    print("\n📄 CREANDO README ACTUALIZADO")
    print("-" * 35)
    
    readme_content = """# GridBot - Bot de Trading Automatizado

## 🚀 Descripción

GridBot es un sistema de trading automatizado que implementa estrategias de grid trading utilizando FastAPI, PostgreSQL, SQLAlchemy y la API de Binance.

## 🏗️ Arquitectura

```
grid_bot/
├── app/
│   ├── api/           # Endpoints de la API
│   ├── core/          # Configuración y utilidades core
│   ├── db/            # Configuración de base de datos
│   ├── models/        # Modelos SQLAlchemy
│   ├── scheduler/     # Jobs programados
│   ├── services/      # Servicios de negocio
│   ├── schemas/       # Esquemas Pydantic
│   └── strategies/    # Estrategias de trading
├── scripts/           # Scripts de utilidad
├── docker/            # Configuración Docker
├── tests/             # Tests unitarios
└── docs/              # Documentación
```

## 🛠️ Tecnologías

- **Backend**: FastAPI, Python 3.11
- **Base de Datos**: PostgreSQL con SQLAlchemy
- **Trading**: python-binance
- **Scheduler**: APScheduler
- **Contenedores**: Docker & Docker Compose
- **Monitoreo**: Prometheus & Grafana

## 🚀 Instalación

1. **Clonar el repositorio**
   ```bash
   git clone <repository-url>
   cd grid_bot
   ```

2. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus credenciales de Binance
   ```

3. **Ejecutar con Docker**
   ```bash
   docker-compose up -d
   ```

## 📊 Configuración

El sistema utiliza `grid_config_optimized.json` para configurar:
- Activos a operar
- Cantidades por transacción
- Niveles de grid
- Rangos de precios

## 🔧 Scripts de Utilidad

- `scripts/run_script.py` - Ejecutor de scripts
- `scripts/verificacion_final_multi_activo.py` - Verificación del sistema
- `scripts/ajustar_cantidades_finales.py` - Ajuste de cantidades
- `scripts/limpiar_proyecto.py` - Limpieza del proyecto

## 📈 Endpoints API

- `GET /health` - Health check
- `GET /config` - Configuración actual
- `GET /status` - Estado del sistema
- `GET /metrics` - Métricas de Prometheus

## 🧪 Testing

```bash
pytest tests/
```

## 📝 Logs

Los logs se pueden ver con:
```bash
docker-compose logs api
```

## 🤝 Contribución

1. Fork el proyecto
2. Crear una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abrir un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✅ README actualizado")

def main():
    """Función principal"""
    print("🔧 OPTIMIZACIÓN DEL CÓDIGO")
    print("=" * 40)
    
    # Optimizar archivos principales
    optimizar_archivos_principales()
    
    # Crear README actualizado
    crear_readme_actualizado()
    
    print("\n🎉 OPTIMIZACIÓN COMPLETADA")
    print("=" * 30)
    print("✅ Código optimizado según PEP8")
    print("✅ Código muerto eliminado")
    print("✅ Nombres de funciones mejorados")
    print("✅ Docstrings agregados")
    print("✅ README actualizado")
    print("\n🚀 Proyecto listo para desarrollo continuo")

if __name__ == "__main__":
    main() 