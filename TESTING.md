# Guía de Pruebas - Creación de Clientes

## ✅ Problema Resuelto

Se ha corregido el error que impedía crear nuevos clientes en la plataforma IAOPS.

### Cambios Aplicados

1. **Compatibilidad Pydantic v2**
   - Actualizado `.dict()` → `.model_dump()`
   - Los métodos deprecados han sido reemplazados

2. **Schemas Flexibles**
   - `created_at` y `updated_at` ahora son opcionales
   - Se asignan automáticamente al crear un cliente

3. **UI Mejorada**
   - Modal completo de creación de clientes
   - Validaciones de formulario
   - Mejor experiencia de usuario

---

## 🚀 Cómo Probar

### Paso 1: Actualizar el Código

```bash
cd /Users/angietatianapena/TWAI-DEMO-IAOPS
git pull origin genspark_ai_developer
```

### Paso 2: Reiniciar Backend (si ya está corriendo)

```bash
docker-compose restart backend
```

O si no usas Docker:
```bash
cd backend
# Ctrl+C para detener el servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Paso 3: Reiniciar Frontend

```bash
# Ctrl+C para detener el servidor actual
cd frontend
npm run dev
```

### Paso 4: Probar la Creación de Clientes

1. **Abrir el navegador**
   - Frontend: http://localhost:3000

2. **Ir a la página de Clientes**
   - Click en "Clientes" en el menú lateral

3. **Crear un Nuevo Cliente**
   - Click en el botón "Nuevo Cliente" (esquina superior derecha)
   - Se abrirá un modal con el formulario

4. **Llenar el Formulario**
   
   **Información Básica:**
   - Nombre: `Empresa Demo`
   - Descripción: `Cliente de prueba para IAOPS`
   
   **Cloud Providers:** (seleccionar al menos uno)
   - ☑️ AWS
   - ☑️ Azure
   - ☐ GCP
   
   **Repositorios:** (seleccionar al menos uno)
   - ☑️ GitHub
   - ☐ GitLab
   - ☐ Bitbucket
   
   **Estándares:**
   - Infraestructura: `Terraform`
   - CI/CD: `GitHub Actions`
   - Orquestación: `kubernetes` (por defecto)
   - Monitoring: `prometheus` (por defecto)

5. **Crear Cliente**
   - Click en "Crear Cliente"
   - Deberías ver un mensaje de éxito
   - El modal se cerrará automáticamente
   - El nuevo cliente aparecerá en la lista

---

## 🔍 Verificación Manual

### Verificar en el Backend

```bash
# Ver logs del backend
docker-compose logs -f backend

# O si no usas Docker, verás los logs en la terminal donde corre uvicorn
```

Deberías ver algo como:
```
INFO Cliente creado: <uuid> - Empresa Demo
```

### Verificar con la API

```bash
# Listar todos los clientes
curl http://localhost:8000/api/v1/clients/ | jq

# Obtener un cliente específico (reemplaza <client_id>)
curl http://localhost:8000/api/v1/clients/<client_id> | jq
```

### Verificar en la UI

1. La tarjeta del nuevo cliente debe aparecer en la lista
2. Debe mostrar:
   - Nombre del cliente
   - Descripción
   - Cloud providers (badges azules)
   - Repositorios (badges morados)
   - Estándares (infraestructura, CI/CD)
3. Botones de "Editar" y "Eliminar" deben estar visibles

---

## 🐛 Solución de Problemas

### Problema: "Error al crear cliente"

**Verificar:**
1. ¿El backend está corriendo?
   ```bash
   curl http://localhost:8000/health
   # Debe devolver: {"status":"healthy","version":"1.0.0"}
   ```

2. ¿El frontend está apuntando al backend correcto?
   - Verificar `frontend/.env`:
   ```
   VITE_API_URL=http://localhost:8000/api/v1
   ```

3. Ver los logs del backend:
   ```bash
   docker-compose logs -f backend
   ```

### Problema: "Modal no se abre"

**Verificar:**
1. En la consola del navegador (F12), ¿hay errores de JavaScript?
2. Refrescar la página (Cmd+R en Mac, Ctrl+R en Windows)
3. Limpiar caché del navegador (Cmd+Shift+R o Ctrl+Shift+R)

### Problema: "Los campos no validan"

**Verificar:**
1. Seleccionaste al menos un Cloud Provider
2. Seleccionaste al menos un Repositorio
3. El nombre no está vacío
4. Los campos de Infraestructura y CI/CD tienen valores

---

## ✨ Características del Modal

### Validaciones Implementadas

- ✅ Nombre es requerido
- ✅ Al menos un cloud provider debe seleccionarse
- ✅ Al menos un repositorio debe seleccionarse
- ✅ Estándares de infraestructura y CI/CD son requeridos
- ✅ Campos opcionales tienen valores por defecto

### Interacción

- **Botones de selección múltiple**: Click para agregar/quitar clouds y repos
- **Color dinámico**: Los botones seleccionados se muestran en color
- **Mensajes de error**: Validaciones se muestran en rojo
- **Feedback visual**: Loading state mientras se crea el cliente
- **Cierre automático**: El modal se cierra después de crear exitosamente

---

## 📊 Ejemplo de Cliente Creado

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Empresa Demo",
  "description": "Cliente de prueba para IAOPS",
  "tech_profile": {
    "clouds": ["aws", "azure"],
    "repositories": ["github"],
    "standards": {
      "infrastructure": "terraform",
      "cicd": "github-actions",
      "container_orchestration": "kubernetes",
      "monitoring": "prometheus",
      "logging": "elk"
    },
    "allowed_services": {},
    "restrictions": {}
  },
  "is_active": true,
  "created_at": "2026-01-20T12:00:00.000000",
  "updated_at": "2026-01-20T12:00:00.000000"
}
```

---

## 🔗 Enlaces Útiles

- **Pull Request**: https://github.com/antape2615/TWAI-DEMO-IAOPS/pull/3
- **Backend API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **MkDocs**: http://localhost:8001

---

## 📞 Soporte

Si encuentras algún problema:

1. Revisa los logs del backend
2. Revisa la consola del navegador (F12)
3. Verifica que todos los servicios estén corriendo
4. Intenta reiniciar los servicios

¿Todo funcionando? 🎉 ¡Perfecto! Ya puedes crear clientes y empezar a usar IAOPS.
