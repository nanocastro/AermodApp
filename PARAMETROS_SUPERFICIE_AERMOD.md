# Parámetros de superficie en AERMOD

El albedo, la razón de Bowen y la longitud de rugosidad describen cómo la
superficie terrestre modifica la capa de aire en la que se dispersa una pluma.
No caracterizan la chimenea: representan el intercambio de radiación, calor y
movimiento entre el suelo y la atmósfera.

En un estudio AERMOD convencional, estos parámetros se introducen en AERMET.
AERMET los utiliza para calcular variables como la turbulencia, la estabilidad,
la velocidad de fricción y la altura de mezcla. AERMOD recibe posteriormente la
meteorología procesada. En esta aplicación, MAKEMET los utiliza para generar
una matriz meteorológica sintética de screening.

## Diferencia entre screening y modelación horaria

Los parámetros tienen el mismo significado físico en ambos modos, pero no
representan necesariamente el mismo lugar ni se agregan de la misma manera.

| Aspecto | Screening con MAKEMET | Modelación horaria con AERMET |
|---|---|---|
| Centro espacial | Fuente de emisión | Estación que midió la meteorología |
| Finalidad | Construir una matriz sintética conservadora | Interpretar cada observación horaria real |
| Rugosidad implementada | 36 sectores de 10° entre 100 y 1000 m | 12 sectores de 30° hasta 1000 m |
| Agregación de rugosidad | Media aritmética por sector y sensibilidad con hasta cinco candidatos | Media geométrica ponderada inversamente por distancia, tipo ZORAD |
| Valor usado | Se busca una envolvente conservadora | Se conserva un valor distinto para cada sector |

En el screening la meteorología sintética se genera para la ubicación de la
fuente. Por eso albedo, Bowen y rugosidad se estiman alrededor de sus
coordenadas. En una corrida horaria con datos de Córdoba Aero o Mendoza Aero,
los parámetros deben describir el entorno de la estación: son necesarios para
obtener la turbulencia y el perfil vertical correspondientes al viento que fue
medido allí.

Si la estación y la fuente tienen entornos muy diferentes, no se corrige la
meteorología reemplazando los parámetros de la estación por los de la fuente.
Esa diferencia debe tratarse como un problema de representatividad de la
estación o mediante meteorología local adicional.

## Albedo

El albedo, normalmente representado por `α`, es la fracción de la radiación
solar incidente que la superficie refleja:

```text
α = radiación reflejada / radiación solar incidente
```

Es adimensional y varía entre 0 y 1.

- Un albedo bajo indica que la superficie absorbe mucha energía. Puede
  corresponder a suelo oscuro, vegetación densa o superficies húmedas.
- Un albedo alto indica que la superficie refleja más radiación. Puede
  corresponder a suelo muy claro, arena o nieve.

Un albedo de `0,14` significa que aproximadamente el 14 % de la radiación
incidente se refleja. El resto queda disponible, con otras pérdidas, para
calentar el suelo y la atmósfera.

### Efecto sobre la dispersión

Un albedo menor suele producir mayor absorción solar, mayor calentamiento
diurno y más posibilidad de turbulencia convectiva. Una atmósfera más turbulenta
mezcla la pluma verticalmente con mayor rapidez. Un albedo mayor suele reducir
el calentamiento superficial y la convección diurna.

Esto no implica una relación universal del tipo «menor albedo = menor
concentración». Una mezcla más intensa puede:

- reducir el máximo en algunos receptores;
- hacer que una pluma elevada llegue antes al suelo;
- cambiar la distancia a la que aparece el máximo.

El resultado también depende de la altura de la chimenea, la flotabilidad de la
pluma, el viento y la estabilidad atmosférica.

### Obtención en la aplicación

La aplicación utiliza el albedo de onda corta de MODIS MCD43A3 y aplica control
de calidad. Calcula un promedio para los dos últimos meses calendario
completos.

## Razón de Bowen

La razón de Bowen expresa cómo se reparte el calor disponible entre:

- `H`: calor sensible, que calienta directamente el aire;
- `LE`: calor latente, utilizado principalmente en evaporación y
  evapotranspiración.

```text
B = H / LE
```

Es un parámetro adimensional. Como interpretación general:

- `B < 1`: domina la evaporación; superficie relativamente húmeda;
- `B ≈ 1`: reparto semejante entre calentamiento y evaporación;
- `B > 1`: domina el calentamiento sensible; superficie relativamente seca;
- un valor muy alto indica que muy poca energía se destina a evaporación.

Por ejemplo, un Bowen de `0,20` indica que el flujo sensible es aproximadamente
una quinta parte del flujo latente durante el período considerado.

### Efecto sobre la dispersión

Con un Bowen alto, una mayor proporción de la energía disponible calienta el
aire. Durante el día esto suele favorecer:

- un mayor flujo de calor sensible;
- convección más intensa;
- mayor velocidad convectiva;
- una capa límite convectiva más desarrollada.

Con un Bowen bajo, una parte mayor de la energía se consume en evaporación y
queda menos disponible para generar turbulencia térmica.

El balance energético superficial simplificado es:

```text
Rn = H + LE + G
```

`Rn` es la radiación neta y `G` es el flujo de calor hacia el suelo. El albedo
ayuda a determinar cuánta radiación queda disponible; Bowen indica cómo se
reparte entre `H` y `LE`. Por eso ambos parámetros actúan conjuntamente.

### Obtención en la aplicación

La aplicación utiliza ERA5-Land y calcula, para las horas válidas:

```text
B = |ΣH / ΣLE|
```

El valor absoluto evita problemas derivados de la convención de signos de los
flujos. Es una aproximación práctica para screening, pero su agregación temporal
y representatividad científica deben revisarse antes de emplearla como valor
regulatorio definitivo.

## Longitud de rugosidad superficial

La longitud de rugosidad, `z₀`, representa la resistencia aerodinámica que la
superficie ofrece al viento. Se expresa en metros.

No es la altura media de los edificios o árboles. Es un parámetro aerodinámico
equivalente relacionado con el tamaño, la densidad y la distribución de los
obstáculos.

Valores orientativos, no universales:

- agua o superficie muy lisa: alrededor de `0,0001 m`;
- suelo abierto o pasto corto: centésimas de metro;
- cultivos o vegetación: décimas de metro;
- bosque, zona industrial o urbana: puede acercarse o superar `1 m`.

La rugosidad interviene en el perfil logarítmico del viento:

```text
U(z) ≈ (u* / κ) ln(z / z₀)
```

donde:

- `U(z)` es la velocidad del viento a la altura `z`;
- `u*` es la velocidad de fricción;
- `κ` es la constante de von Kármán;
- `z₀` es la longitud de rugosidad.

### Efecto sobre la dispersión

Una rugosidad mayor generalmente produce:

- mayor fricción superficial;
- mayor turbulencia mecánica;
- cambios en el perfil vertical del viento;
- cambios en la estabilidad y en la altura de mezcla;
- mayor interacción de la pluma con la capa próxima al suelo.

La respuesta de la concentración no es necesariamente monotónica. Una mayor
rugosidad puede aumentar la dilución, pero también modificar la elevación y el
descenso de la pluma o acercar el máximo a la fuente.

La rugosidad es especialmente sensible a la dirección. Alrededor de una misma
fuente puede haber ciudad, cultivos, bosque y terreno abierto. Por eso es más
representativo calcularla por sectores que utilizar un único promedio
omnidireccional.

### Obtención en la aplicación

La aplicación clasifica ESA WorldCover dentro de un anillo de 100 a 1000 m
alrededor de la fuente y calcula 36 sectores de 10°. Después:

1. convierte las clases de cobertura en valores de `z₀`;
2. calcula una rugosidad para cada dirección;
3. forma hasta cinco candidatos representativos, conservando los extremos;
4. en terreno complejo ejecuta una sensibilidad con AERMOD;
5. selecciona el candidato que produce la mayor concentración.

Este procedimiento es más conservador que seleccionar directamente una
rugosidad promedio.

### Cómo se convierte la cobertura del suelo en rugosidad

ESA WorldCover no contiene valores aerodinámicos: cada píxel de 10 m contiene
un código de cobertura, como árboles, pastizal, cultivos, superficie construida
o suelo desnudo. La conversión se realiza en dos etapas.

Primero, cada código se transforma en una longitud de rugosidad mediante una
correspondencia documentada. WorldCover no proporciona `z₀`, por lo que se
eligió la clase NLCD equivalente de AERSURFACE. Cuando WorldCover no tiene un
equivalente suficientemente específico en NLCD se adoptó el tipo de vegetación
de ECMWF más próximo.

Los perfiles estacionales son:

- verano con vegetación desarrollada: diciembre–febrero;
- otoño con cultivos aún no cosechados: marzo–mayo;
- invierno sin cobertura continua de nieve: junio–agosto;
- primavera de transición: septiembre–noviembre;
- invierno con nieve: solo si existe cobertura continua, situación que no se
  adoptó para Córdoba Aero ni Mendoza Aero.

Las estaciones están expresadas para el hemisferio sur. Los valores de
AERSURFACE mantienen su definición física original; solamente se trasladaron
los meses del calendario.

| WorldCover | Cobertura y correspondencia | Verano | Inv. nieve | Inv. sin nieve | Primavera | Otoño | Fuente |
|---:|---|---:|---:|---:|---:|---:|---|
| 10 | Árboles → NLCD 43, bosque mixto | 0,900 | 0,800 | 1,100 | 1,300 | 1,300 | EPA |
| 20 | Matorral → NLCD 52, no árido | 0,300 | 0,150 | 0,300 | 0,300 | 0,300 | EPA |
| 30 | Pastizal → NLCD 71 | 0,010 | 0,005 | 0,050 | 0,100 | 0,100 | EPA |
| 40 | Cultivos → NLCD 82 | 0,030 | 0,014 | 0,040 | 0,200 | 0,200 | EPA |
| 40-A | Cultivos en aeropuerto | 0,020 | 0,010 | 0,020 | 0,030 | 0,030 | EPA |
| 50 | Construido → NLCD 23, intensidad media | 0,300 | 0,200 | 0,300 | 0,300 | 0,300 | EPA |
| 50-A | Construido en aeropuerto | 0,050 | 0,040 | 0,060 | 0,060 | 0,060 | EPA |
| 60 | Suelo desnudo/vegetación escasa → NLCD 31, no árido | 0,050 | 0,010 | 0,050 | 0,050 | 0,050 | EPA |
| 70 | Nieve/hielo → NLCD 12 | 0,002 | 0,002 | 0,002 | 0,002 | 0,002 | EPA |
| 80 | Agua permanente → NLCD 11 | 0,001 | 0,001 | 0,001 | 0,001 | 0,001 | EPA |
| 90 | Humedal herbáceo → NLCD 95 | 0,200 | 0,100 | 0,200 | 0,200 | 0,200 | EPA |
| 95 | Manglar → NLCD 91, humedal leñoso | 0,400 | 0,300 | 0,500 | 0,500 | 0,500 | EPA |
| 100 | Musgo/líquenes → tundra | 0,034 | 0,034 | 0,034 | 0,034 | 0,034 | ECMWF |

La fuente EPA es la tabla de rugosidades estacionales de AERSURFACE 26135. El
único respaldo ECMWF necesario en esta correspondencia es la rugosidad de
`0,034 m` para tundra, adoptada para musgos y líquenes, tomada de la Tabla 11.4
de la documentación física del IFS. La elección de “intensidad media” para el
código construido es necesaria porque WorldCover no informa densidad urbana.
Se conserva explícitamente para que pueda revisarse si se incorpora una capa
de impermeabilización o altura de edificios.

Para matorral y suelo desnudo se adoptaron las variantes EPA no áridas. EPA
permite seleccionar perfiles áridos, pero la aplicación todavía no tiene un
campo climático explícito. La variante no árida produce la rugosidad más alta
para el matorral y evita subestimarla por una clasificación automática no
documentada. Esta decisión debe revisarse si se incorpora una capa climática o
una selección del usuario.

En screening se usan las filas normales. Para meteorología medida en Córdoba
Aero y Mendoza Aero se usan las filas `40-A` y `50-A`, siguiendo el tratamiento
aeroportuario de EPA. La misma tabla y el mismo código de conversión alimentan
ambos modos; cambia únicamente el contexto aeroportuario y la forma de agregar
los píxeles.

Segundo, los valores de todos los píxeles de un sector se combinan. Para la
modelación horaria se implementó una adaptación del método ZORAD de
AERSURFACE:

1. se centra un círculo de 1000 m de radio en el anemómetro;
2. se divide el círculo en 12 sectores de 30°, medidos desde el norte y en
   sentido horario;
3. cada píxel se asigna al sector desde el cual llegaría el viento a la
   estación;
4. su clase WorldCover se convierte en `z₀` mediante la tabla anterior;
5. se da mayor peso a las coberturas cercanas al anemómetro;
6. se calcula una media geométrica ponderada para cada sector.

La ecuación es:

```text
wᵢ = 1 / max(dᵢ, 5 m)

z₀,sector = exp[ Σ(wᵢ · ln(z₀,ᵢ)) / Σwᵢ ]
```

`dᵢ` es la distancia entre el centro del píxel y el anemómetro. El límite de
`5 m` corresponde a media celda WorldCover y evita un peso infinito si el
anemómetro coincide con el centro de un píxel. La media es geométrica porque
la rugosidad varía por órdenes de magnitud: mezclar agua, suelo, cultivos y
edificios con una media aritmética permitiría que unos pocos valores altos
dominaran el sector.

La implementación oficial de AERSURFACE usa coberturas y tablas NLCD de
Estados Unidos. Por lo tanto, reproducir su agregación espacial con WorldCover
es un procedimiento **análogo a ZORAD**, no una ejecución oficial de
AERSURFACE.

### Rugosidades sectoriales de las estaciones

Se aplicó el procedimiento anterior a ESA WorldCover 2021 v200, usando las
coordenadas `−31,317; −64,217` para Córdoba Aero y `−32,833; −68,783` para
Mendoza Aero.

| Sector de viento | Centro | Córdoba Aero | Mendoza Aero |
|---:|---:|---:|---:|
| 0°–30° | 15° | 0,0501 m | 0,1304 m |
| 30°–60° | 45° | 0,0606 m | 0,1586 m |
| 60°–90° | 75° | 0,0547 m | 0,1458 m |
| 90°–120° | 105° | 0,0550 m | 0,1711 m |
| 120°–150° | 135° | 0,0535 m | 0,1999 m |
| 150°–180° | 165° | 0,0294 m | 0,2164 m |
| 180°–210° | 195° | 0,0290 m | 0,1525 m |
| 210°–240° | 225° | 0,0438 m | 0,1578 m |
| 240°–270° | 255° | 0,0537 m | 0,1061 m |
| 270°–300° | 285° | 0,0619 m | 0,0772 m |
| 300°–330° | 315° | 0,0477 m | 0,0940 m |
| 330°–360° | 345° | 0,0537 m | 0,0903 m |

Estos valores deben introducirse por sector en AERMET. No corresponde elegir
el máximo para todas las horas: AERMET selecciona la rugosidad asociada a la
dirección horaria del viento. Los resultados completos conservan también la
cantidad de píxeles de cada clase para auditoría y pueden reproducirse con
`scripts/calculate_station_roughness.py`.

La comparación con el screening ilustra la diferencia metodológica:

| Estación | Máximo de screening | Rango sectorial tipo ZORAD |
|---|---:|---:|
| Córdoba Aero | 0,2586 m | 0,0290–0,0619 m |
| Mendoza Aero | 0,2735 m | 0,0772–0,2164 m |

La disminución no significa que haya cambiado la cobertura. Resulta de usar
sectores más anchos, incluir el entorno inmediato al anemómetro, aplicar una
media geométrica ponderada y usar el ajuste aeroportuario de EPA en la corrida
horaria, en lugar de una media aritmética conservadora no aeroportuaria.

## Relación entre los tres parámetros

| Parámetro | Describe | Influye principalmente en |
|---|---|---|
| Albedo | Radiación solar reflejada | Energía disponible para calentar la superficie |
| Razón de Bowen | Reparto entre calentamiento y evaporación | Turbulencia térmica y convección |
| Rugosidad | Resistencia aerodinámica al viento | Turbulencia mecánica y perfil del viento |

Una forma sencilla de recordarlos:

- **Albedo:** ¿cuánta energía solar absorbe el terreno?
- **Bowen:** ¿esa energía calienta el aire o evapora agua?
- **Rugosidad:** ¿cuánto frenan y agitan el viento los obstáculos?

## Representatividad y precauciones

En screening, estos parámetros deberían representar el entorno de la fuente.
En modelación horaria, deberían representar el entorno de las observaciones
meteorológicas. Dos lugares próximos pueden tener superficies muy diferentes,
como un aeropuerto, una zona urbana, cultivos irrigados o un bosque.

En la aplicación son valores editables y se conserva su procedencia. Los
resultados obtenidos de MODIS, ERA5-Land y WorldCover constituyen estimaciones
técnicas reproducibles para screening. No equivalen automáticamente a una
selección regulatoria ni científicamente aprobada.

## Referencias

- [EPA — AERMOD Implementation Guide](https://gaftp.epa.gov/aqmg/SCRAM/models/preferred/aermod/aermod_implementation_guide.pdf)
- [EPA — User's Guide for the AERSURFACE Tool](https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/aersurface/aersurface_userguide.pdf)
- [EPA — Código fuente de AERSURFACE 26135](https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/aersurface/aersurface_source.zip)
- [ECMWF — IFS Documentation, Part IV: Physical Processes, Table 11.4](https://confluence.ecmwf.int/download/attachments/19661682/IFS_CY38R1_Part4.pdf?api=v2&download=true&modificationDate=1443006083445&version=1)
- [ESA — WorldCover 2021 v200 y manual del producto](https://esa-worldcover.org/en/data-access)
- [EPA — AERMET User's Guide](https://gaftp.epa.gov/Air/aqmg/SCRAM/models/met/aermet/aermet_userguide.pdf)
- [EPA — AERSCREEN User's Guide](https://gaftp.epa.gov/Air/aqmg/SCRAM/models/screening/aerscreen/aerscreen_userguide.pdf)
