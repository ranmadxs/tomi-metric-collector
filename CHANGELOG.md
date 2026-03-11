# Changelog

## [1.6.8] - 2025-03-11

### Added
- render.yaml para deploy en Render
- hora_local como clave única en MongoDB (evita duplicados)
- Upsert en lugar de insert para estanque-historial

### Changed
- Monitor y MQTT worker usan update_one con upsert

---

## [1.5.0] - 2025-03-10

### Added
- Sistema de autenticación (login/logout) con sesiones Flask
- Template login.html
- Home (/) protegido con login obligatorio
- Monitor (/monitor) público con botón Login/Salir
- Simulador de Niveles solo visible para admin
- Historial detallado en popup con gráfico por horas del mes
- Zoom interactivo: clic en día para ver detalle por hora
- Eje Y en litros (0-5000 L) en lugar de porcentaje
- Zona horaria Chile (America/Santiago) para horas correctas
- Botón Salir con redirección según página actual

### Fixed
- Fechas del gráfico (problema UTC en zona horaria)
- API historial mensual retorna JSON 401 en lugar de redirect

---

## [1.4.x] - Historial anterior

- Monitor de estanque con MQTT
- Gráfico historial mensual
- Conexión MongoDB lazy
- Validación DataDog y MongoDB

---

## [0.1.10] - 05-nov-2024
- 🌟 Feature: Async Logs

## [0.1.8] - 05-nov-2024
- 🌟 Feature: Add Method Post Logs