<?php
echo "<h3>Diagnostico de conexion desde PHP en Docker</h3>";
echo "RUNNING_IN_DOCKER (getenv): '" . getenv('RUNNING_IN_DOCKER') . "'<br>";
echo "_ENV['RUNNING_IN_DOCKER']: '" . (isset($_ENV['RUNNING_IN_DOCKER']) ? $_ENV['RUNNING_IN_DOCKER'] : 'No seteado') . "'<br>";
echo "_SERVER['RUNNING_IN_DOCKER']: '" . (isset($_SERVER['RUNNING_IN_DOCKER']) ? $_SERVER['RUNNING_IN_DOCKER'] : 'No seteado') . "'<br>";

$host = (getenv('RUNNING_IN_DOCKER') === 'yes' || (isset($_SERVER['RUNNING_IN_DOCKER']) && $_SERVER['RUNNING_IN_DOCKER'] === 'yes')) ? 'db' : '127.0.0.1';
$port = ($host === 'db') ? 3306 : 3307;

echo "Intentando conectar a host: '$host', puerto: $port, usuario: 'root', BD: 'cacti'...<br>";

try {
    $link = mysqli_connect($host, 'root', '', 'cacti', $port);
    if ($link) {
        echo "<h3>✅ ¡Conexion exitosa a la base de datos 'cacti'!</h3>";
        mysqli_close($link);
    } else {
        echo "<h3>❌ Fallo la conexion: " . mysqli_connect_error() . "</h3>";
    }
} catch (Exception $e) {
    echo "<h3>❌ Excepcion capturada: " . $e->getMessage() . "</h3>";
}
