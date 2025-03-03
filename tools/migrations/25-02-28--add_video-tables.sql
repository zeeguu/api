CREATE TABLE `zeeguutest`.`video` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `platform_id` VARCHAR(512) NULL,
  `title` VARCHAR(512) NULL,
  `channel_id` INT NULL,
  `content` MEDIUMTEXT NULL,
  `subtitles` MEDIUMTEXT NULL,
  `description` MEDIUMTEXT NULL,
  `thumbnail` MEDIUMTEXT NULL,
  `duration` INT NULL,
  `language_id` INT NULL,
  PRIMARY KEY (`id`),
  INDEX `channel_id_idx` (`channel_id` ASC),
  INDEX `language_id_idx` (`language_id` ASC),
  CONSTRAINT `channel_id_fk`
    FOREIGN KEY (`channel_id`)
    REFERENCES `zeeguutest`.`yt_channel` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `language_id_fk`
    FOREIGN KEY (`language_id`)
    REFERENCES `zeeguutest`.`language` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
);


CREATE TABLE `zeeguutest`.`yt_channel` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(512) NULL,
  `channel_id` VARCHAR(512) NULL,
  `views` INT NULL,
  `subscribers` INT NULL,
  `language_id` INT NULL,
  `rss_url` MEDIUMTEXT NULL,
  PRIMARY KEY (`id`)
  INDEX `language_id_idx` (`language_id` ASC);
  CONSTRAINT `channel_language_id`
    FOREIGN KEY (`language_id`)
    REFERENCES `zeeguutest`.`language` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION;
  );


CREATE TABLE `zeeguutest`.`subtitle_line` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `video_id` INT NULL,
  `start_time` TIME NULL,
  `end_time` TIME NULL,
  PRIMARY KEY (`id`),
  INDEX `video_id_idx` (`video_id` ASC),
  CONSTRAINT `video_id`
    FOREIGN KEY (`video_id`)
    REFERENCES `zeeguutest`.`video` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION);


INSERT INTO yt_channel(name, channel_id, views, subscribers, language_id, rss_url) VALUES ('Naturen i Danmark', 'UCMNMJW01ZNlSERud6oUnMyg', 756786, 8260, 2, 'https://www.youtube.com/feeds/videos.xml?channel_id=UCMNMJW01ZNlSERud6oUnMyg');
INSERT INTO video (platform_id, title, channel_id, content, subtitles, description, thumbnail, duration, language_id)
VALUES (
    'EWnStY9O4CA', 
    '5 SMÅ Naturperler du aldrig har hørt om // Dansk natur', 
    1, 
    'blabla', 
    'blablabla', 
    'Se mere og find kontakt oplysninger på:
    www.naturenidanmark.dk

    Denne film er produceret af Naturen I Danmark – et filmproduktionsselskab, der skaber naturfilm til formidling af dansk natur. Besøg vores hjemmeside www.naturenidanmark.dk for at se mere om vores arbejde, eller kontakt os, hvis du har brug for en unik film til dit projekt. Vi hjælper kommuner, organisationer og andre med at fortælle naturens historier gennem smukke og stemningsfulde optagelser.

    Oplev en smuk dansk naturfilm, der præsenterer fem oversete naturperler i Danmark. I denne inspirerende naturdokumentar fra Danmark tager vi dig med til unikke steder som Tingvad Kær, de fortryllende Syvårssøerne, den krystalklare Store Blåkilde, den urørte Draved Skov, og den eventyrlige Allindelille Fredskov. Disse skjulte skatte i den danske natur byder på enestående landskaber og fascinerende historier, som gør dem til oplagte mål for naturoplevelser.

    Filmen er en del af vores arbejde med naturformidling på film og formidling af naturgenopretning i Danmark. Den viser, hvordan naturen i Danmark kan inspirere og begejstre med smukke danske naturklip og stemningsfulde optagelser. Hvis du elsker naturfilm fra Danmark og søger nye steder at udforske, er denne film skabt for dig.

    Følg med og lad dig fascinere af smuk dansk naturfilm, der bringer de mest naturskønne danske områder frem i lyset. Perfekt til naturelskere, kommuner og organisationer, der arbejder med naturformidling og ønsker at opleve, hvordan naturklip fra Danmark kan inspirere til både bevarelse og genopretning.', 
    'https://i.ytimg.com/vi/EWnStY9O4CA/hqdefault.jpg', 
    609, 
    2
);