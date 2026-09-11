# cAdvisor — stubs para Docker Desktop / hosts sin systemd DMI

Estos archivos no son secretos.

- `machine-id` → montado en `/etc/machine-id` y `/rootfs/etc/machine-id`
  (Desktop no tiene systemd machine-id; sin el stub, housekeeping loguea E/W).

## `gce.go` / `product_name` (esperado en Mac)

cAdvisor sondea si corre en GCE leyendo `/sys/class/dmi/id/product_name`.
En Docker Desktop (LinuxKit) **no existe** `/sys/class/dmi`. El log es **Info**
(`I… gce.go:45`), cada ~5 min, no un crash:

`Error while reading product_name: open /sys/class/dmi/id/product_name: no such file or directory`

No se puede stubear: sysfs no deja `mkdir` de nodos DMI, y un bind a
`/sys/class/dmi/id` falla porque `/sys` está `:ro` (read-only file system).
No montar DMI sobre `/sys`.

Señal real de salud: `up{job="cadvisor"}==1` y
`count(container_cpu_usage_seconds_total{id!="/"}) >= 1`, no la ausencia de
ese Info. Paper-only. **PROMOTE_LIVE: NO.**
