FROM php:8.1-apache

# Install and enable both mysqli and pdo_mysql extensions required by Cacti
RUN docker-php-ext-install mysqli pdo_mysql && docker-php-ext-enable mysqli pdo_mysql
