import sys
import pygame
import random
import math

from scripts.entities import Player, Enemy
from scripts.utils import load_image, load_images, Animation
from scripts.tilemap import Tilemap
from scripts.clouds import Clouds
from scripts.particles import Particle
from scripts.spark import Spark


class Game:
	def __init__(self):
		pygame.init()

		pygame.display.set_caption('ninja game')

		# res - (960 x 720) | (640 x 480)
		self.screen = pygame.display.set_mode((640, 480))

		self.display = pygame.Surface((320, 240), pygame.SRCALPHA)
		self.display_2 = pygame.Surface((320, 240))

		self.clock = pygame.time.Clock()

		self.movement = [False, False]

		self.assets = {
			'decor': load_images('tiles/decor'),
			'grass': load_images('tiles/grass'),
			'large_decor': load_images('tiles/large_decor'),
			'stone': load_images('tiles/stone'),
			'player': load_image('entities/player.png'),
			'background': load_image('background.png'),
			'clouds': load_images('clouds'),
			'enemy/idle': Animation(load_images('entities/enemy/idle'), img_dur=6),
			'enemy/run': Animation(load_images('entities/enemy/run'), img_dur=4),
			'player/idle': Animation(load_images('entities/player/idle'), img_dur=6),
			'player/run': Animation(load_images('entities/player/run'), img_dur=4),
			'player/jump': Animation(load_images('entities/player/jump')),
			'player/slide': Animation(load_images('entities/player/slide')),
			'player/wall_slide': Animation(load_images('entities/player/wall_slide')),
			'particle/leaf': Animation(load_images('particles/leaf'), img_dur=20, loop=False),
			'particle/particle': Animation(load_images('particles/particle'), img_dur=6, loop=False),
			'gun': load_image('gun.png'),
			'projectile': load_image('projectile.png')
		}

		self.sfx = {
			'jump': pygame.mixer.Sound('data/sfx/jump.wav'),
			'shoot': pygame.mixer.Sound('data/sfx/shoot.wav'),
			'dash': pygame.mixer.Sound('data/sfx/dash.wav'),
			'ambience': pygame.mixer.Sound('data/sfx/ambience.wav'),
			'hit': pygame.mixer.Sound('data/sfx/hit.wav')
		}

		self.sfx['ambience'].set_volume(0.2)
		self.sfx['shoot'].set_volume(0.4)
		self.sfx['hit'].set_volume(0.8)
		self.sfx['dash'].set_volume(0.3)
		self.sfx['jump'].set_volume(0.7)

		self.clouds = Clouds(self.assets['clouds'], count=16)

		self.player = Player(self, (50, 50), [8, 15])

		self.tile_map = Tilemap(self, tile_size=16)

		try:
			self.tile_map.load('map.json')
		except FileNotFoundError:
			pass

		self.leaf_spawners = []
		for tree in self.tile_map.extract([('large_decor', 2)], keep=True):
			self.leaf_spawners.append(pygame.Rect(4 + tree['pos'][0], 4 + tree['pos'][1], 23, 13))

		self.enemies = []

		for spawner in self.tile_map.extract([('spawners', 0), ('spawners', 1)], keep=False):
			if spawner['variant'] == 0:
				self.player.pos = spawner['pos']
				self.player.air_time = 0
			else:
				self.enemies.append(Enemy(self, spawner['pos'], (8, 15)))

		self.projectiles = []
		self.particles = []
		self.sparks = []

		self.scroll = [0, 0]
		self.dead = 0
		self.transition = -30

		self.screen_shake = 0

	def run(self):
		pygame.mixer.music.load('data/music.wav')
		pygame.mixer.music.set_volume(0.5)
		pygame.mixer.music.play(-1)

		self.sfx['ambience'].play(-1)
		while True:
			self.display.fill((0, 0, 0, 0))
			self.display_2.blit(self.assets['background'], (0, 0))

			self.screen_shake = max(0, self.screen_shake - 1)

			if not len(self.enemies):
				self.transition += 1
				self.sfx['ambience'].stop()
				pygame.mixer.music.stop()
				if self.transition > 30:
					pygame.quit()
					break
			if self.transition < 0:
				self.transition += 1

			if self.dead:
				self.dead += 1
				if self.dead > 40:
					self.transition += 1
					self.sfx['ambience'].stop()
					pygame.mixer.music.stop()
					if self.transition > 30:
						pygame.quit()
						break

			self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 30
			self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.scroll[1]) / 30

			render_scroll = (int(self.scroll[0]), int(self.scroll[1]))

			for rect in self.leaf_spawners:
				if random.random() * 49999 < rect.width * rect.height:
					pos = (rect.x + random.random() * rect.width, rect.y + random.random() * rect.height)
					self.particles.append(Particle(self, 'leaf', pos, velocity=[-0.1, 0.3], frame=random.randint(0, 20)))

			self.clouds.update()
			self.clouds.render(self.display, offset=render_scroll)

			self.tile_map.render(self.display, offset=render_scroll)

			for enemy in self.enemies.copy():
				kill = enemy.update(self.tile_map, (0, 0))
				enemy.render(self.display, offset=render_scroll)
				if kill:
					self.enemies.remove(enemy)

			self.player.update(self.tile_map, (self.movement[1] - self.movement[0], 0))
			self.player.render(self.display, offset=render_scroll)

			for projectile in self.projectiles.copy():
				projectile[0][0] += projectile[1]
				projectile[2] += 1
				img = self.assets['projectile']
				self.display.blit(img, (
					projectile[0][0] - img.get_width() / 2 - render_scroll[0],
					projectile[0][1] - img.get_height() / 2 - render_scroll[1]))
				if self.tile_map.solid_check(projectile[0]):
					self.projectiles.remove(projectile)
					for i in range(4):
						self.sparks.append(Spark(
							projectile[0],
							random.random() - 0.5 + (math.pi if projectile[1] > 0 else 0),
							2 + random.random()))
				elif projectile[2] > 360:
					self.projectiles.remove(projectile)
				elif abs(self.player.dashing) < 50:
					if self.player.rect().collidepoint(projectile[0]):
						self.projectiles.remove(projectile)
						self.dead += 1
						self.sfx['hit'].play()
						self.screen_shake = max(16, self.screen_shake)
						for i in range(30):
							angle = random.random() * math.pi * 2
							speed = random.random() * 5
							self.sparks.append(Spark(self.player.rect().center, angle, 2 + random.random()))
							self.particles.append(Particle(
								self, 'particle', self.player.rect().center,
								velocity=[
									math.cos(angle + math.pi) * speed * 0.5,
									math.sin(angle + math.pi) * speed * 0.5],
								frame=random.randint(0, 7)))

			for spark in self.sparks.copy():
				kill = spark.update()
				spark.render(self.display, offset=render_scroll)
				if kill:
					self.sparks.remove(spark)

			display_mask = pygame.mask.from_surface(self.display)
			display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
			for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
				self.display_2.blit(display_silhouette, offset)

			for particle in self.particles.copy():
				kill = particle.update()
				particle.render(self.display, offset=render_scroll)
				if particle.type == 'leaf':
					particle.pos[0] += math.sin(particle.animation.frame * 0.035) * 0.3
				if kill:
					self.particles.remove(particle)

			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()
				if event.type == pygame.KEYDOWN:
					if event.key == pygame.K_LEFT:
						self.movement[0] = True
					if event.key == pygame.K_RIGHT:
						self.movement[1] = True
					if event.key == pygame.K_UP:
						if self.player.jump():
							self.sfx['jump'].play()
					if event.key == pygame.K_x:
						self.player.dash()
				if event.type == pygame.KEYUP:
					if event.key == pygame.K_LEFT:
						self.movement[0] = False
					if event.key == pygame.K_RIGHT:
						self.movement[1] = False

			if self.transition:
				transition_surf = pygame.Surface(self.display.get_size())
				pygame.draw.circle(
					transition_surf, (255, 255, 255),
					(self.display.get_width() // 2, self.display.get_height() // 2),
					(30 - abs(self.transition)) * 8)
				transition_surf.set_colorkey((255, 255, 255))
				self.display.blit(transition_surf, (0, 0))

			screen_shake_offset = (
				random.random() * self.screen_shake - self.screen_shake / 2,
				random.random() * self.screen_shake - self.screen_shake / 2)

			self.display_2.blit(self.display, (0, 0))

			self.screen.blit(pygame.transform.scale(self.display_2, self.screen.get_size()), screen_shake_offset)
			pygame.display.update()
			self.clock.tick(60)


while True:
	Game().run()
