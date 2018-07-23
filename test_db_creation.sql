
create database IF NOT EXISTS zeeguu_test; 
CREATE USER 'zeeguu_test'@'localhost' IDENTIFIED BY 'zeeguu_test';
grant all on zeeguu_test.* to 'zeeguu_test'@'localhost';
flush privileges;