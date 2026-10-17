<?php

declare(strict_types=1);

use Rector\Config\RectorConfig;
use Rector\Set\ValueObject\LevelSetList;

$target = getenv('OLDWEBSITES_PHP_TARGET') ?: '8.5';
$sets = [
    '8.1' => LevelSetList::UP_TO_PHP_81,
    '8.2' => LevelSetList::UP_TO_PHP_82,
    '8.3' => LevelSetList::UP_TO_PHP_83,
    '8.4' => LevelSetList::UP_TO_PHP_84,
    '8.5' => LevelSetList::UP_TO_PHP_85,
];

if (!isset($sets[$target])) {
    throw new RuntimeException(sprintf('Unsupported PHP target: %s', $target));
}

return RectorConfig::configure()->withSets([$sets[$target]]);