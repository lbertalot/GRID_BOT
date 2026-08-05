# cAdvisor — stubs para Docker Desktop / hosts sin systemd DMI

Estos archivos no son secretos. Evitan logs E/W de cAdvisor cuando el host
(p. ej. macOS + Docker Desktop) no expone `/etc/machine-id` ni DMI GCE.

- `machine-id` → montado en `/etc/machine-id` y `/rootfs/etc/machine-id`
- `product_name` (opcional) → `/sys/class/dmi/id/product_name` si el bind es permitido
