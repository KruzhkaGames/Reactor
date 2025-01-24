# coding=utf-8

# Инициализация библиотек :>

import pybullet, time, os, math, sys
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import numpy as np
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from termcolor import colored

time.sleep(0.01)
sys.stdout.write("\033[F\033[K")
sys.stdout.flush()


# Лоадер 8)

class Loader:
    def __init__(self):
        pass

    def texture_loader(self, filename):
        """Загрузка текстуры из файла."""
        filename = os.path.join(filename)
        texture_surface = pygame.image.load(filename)
        texture_data = pygame.image.tostring(texture_surface, 'RGB', True)
        width = texture_surface.get_width()
        height = texture_surface.get_height()

        texid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texid)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, texture_data)

        # Установка параметров текстуры
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glGenerateMipmap(GL_TEXTURE_2D)  # Генерация мипмапов для улучшения качества текстуры

        glBindTexture(GL_TEXTURE_2D, 0)
        return texid

def MTL(loader, filename):
    """Загрузка материалов из MTL файла."""
    contents = {}
    mtl = None
    for line in open(filename, "r"):
        if line.startswith('#'): continue
        values = line.split()
        if not values: continue
        if values[0] == 'newmtl':
            mtl = contents[values[1]] = {}
        elif mtl is None:
            continue
        elif values[0] == 'map_Kd':
            # Загрузка текстуры для материала
            mtl['texture'] = loader.texture_loader(os.path.join(os.path.dirname(filename), values[1]))
    return contents

def OBJ(filename, loader, swapyz=False):
    """Загрузка OBJ файла."""
    vertices = []
    textures = []
    faces = []
    mtllib = None
    mtl = None

    for line in open(filename, "r"):
        if line.startswith('#'): continue
        values = line.split()
        if not values: continue
        if values[0] == 'v':
            # Загрузка вершин
            v = list(map(float, values[1:4]))
            if swapyz:
                v = v[0], v[2], v[1]
            vertices.append(v)
        elif values[0] == 'vt':
            # Загрузка текстурных координат
            t = list(map(float, values[1:3]))
            textures.append(t)
        elif values[0] == 'f':
            # Загрузка полигонов (граней)
            face = []
            tex_face = []
            for v in values[1:]:
                w = v.split('/')
                face.append(int(w[0]) - 1)
                if len(w) > 1 and w[1]:
                    tex_face.append(int(w[1]) - 1)
                else:
                    tex_face.append(0)
            faces.append((face, tex_face))
        elif values[0] == 'mtllib':
            # Загрузка MTL файла
            mtllib = values[1]

    if mtllib:
        mtl = MTL(loader, os.path.join(os.path.dirname(filename), mtllib))

    return {
        'vertices': vertices,
        'textures': textures,
        'faces': faces,
        'mtl': mtl
    }


# Окошко :>

_have_space = False
_window = False
_debg = True

class Window:
    """Класс Window является графическим движком Реактора. Он создаёт окно, где параллельно происходят вычисления графики и отрисовка."""

    def __init__(self, window_size, win_name, win_icon):
        """Создаём окошко."""

        self._window = pygame.display.set_mode(window_size, DOUBLEBUF | OPENGL)
        pygame.display.set_caption(win_name)
        if win_icon is not None:
            pygame.display.set_icon(pygame.image.load(win_icon))
        
        # Задаём базовые значения для вычислений в PyOpenCV
        gluPerspective(70, (window_size[0] / window_size[1]), 0.1, 100.0)
        self._camera = [(window_size[0] / window_size[1]), (0, 0, 0), (0, 0, 1), (0, 1, 0), 0.1, 100.0]
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        # Создаём загрузчик текстурок и данные для хранения информации об объектах.
        self._loader = Loader()
        self._objects = []

        # Задний фон, размеры окна и прочие шняги.
        self._background_color = (0, 0, 0)
        self._window_size = window_size
        self._fovy = 70
        self._surface = pygame.Surface(window_size)
        self._pictures = []
        self._background = None

        self.debug("Успешная инициализация PyGame и PyOpenGL.")

    def render(self):
        """Главная функция класса Window, где происходит отрисовка. Возвращает pygame.Surface с результатом."""

        # Сброс
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glScalef(-1, 1, 1)

        eyeX, eyeY, eyeZ = self._camera[1]
        centerX, centerY, centerZ = self._camera[2]
        upX, upY, upZ = self._camera[3]
        gluPerspective(70, self._camera[0], self._camera[4], self._camera[5])
        gluLookAt(
            eyeX, eyeY, eyeZ,
            centerX, centerY, centerZ,
            upX, upY, upZ)
        
        if self._background is not None:
            self._render_background(self._background_sphere, self._background_texture_id)


        # Отрисовка объектов
        
        for obj in self._objects:
            if obj[4]:
                glPushMatrix()
                glTranslatef(*obj[1])

                qw, qx, qy, qz = obj[2]
                xx = qx * qx
                yy = qy * qy
                zz = qz * qz
                xy = qx * qy
                xz = qx * qz
                yw = qy * qw
                zw = qz * qw
                xw = qx * qw
                yz = qy * qz
                mat = [
                    1 - 2 * (yy + zz),    2 * (xy - zw),       2 * (xz + yw),       0.0,
                    2 * (xy + zw),        1 - 2 * (xx + zz),   2 * (yz - xw),       0.0,
                    2 * (xz - yw),        2 * (yz + xw),       1 - 2 * (xx + yy),   0.0,
                    0.0,                  0.0,                 0.0,                 1.0
                ]

                glMultMatrixf(mat)

                glScalef(*obj[3])

                def draw_object(o):
                    for face in o['faces']:
                        face_vertices, face_textures = face
                        material_name = 'Material'  # Имя материала (должно совпадать с MTL файлом)
                        if o['mtl'] and material_name in o['mtl']:
                            glBindTexture(GL_TEXTURE_2D, o['mtl'][material_name]['texture'])
                        else:
                            glBindTexture(GL_TEXTURE_2D, 0)

                        glBegin(GL_POLYGON)
                        for i in range(len(face_vertices)):
                            if face_textures[i] < len(o['textures']):
                                tx, ty = o['textures'][face_textures[i]]
                                glTexCoord2f(tx, ty)
                            glVertex3fv(o['vertices'][face_vertices[i]])
                        glEnd()

                draw_object(obj[0])
                glPopMatrix()
        
        # Отрисовка картинок
        for pic in self._pictures:
            self._draw_textured_panel(self._surface_to_opengl_texture(pic[0]), pic[1], pic[2], pic[3][0] * 2, pic[3][1])
        
        self._pictures.clear()

        # Захват результата (скриншот)
        width, height = self._window_size
        buffer = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
        surface = pygame.image.frombuffer(buffer, (width, height), "RGBA")
        surface = pygame.transform.flip(surface, False, True)

        # Отрисовка текущего состояния экрана PyGame (создание параллельности вычислений и графики)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluLookAt(0, 0, 0, 0, 0, 1, 0, 1, 0)
        self._draw_textured_panel(self._surface_to_opengl_texture(pygame.transform.flip(self._surface, True, False)), (0, 0, 1), (1, 0, 0, 0), 2, 2)

        return surface
    
    def load_model(self, filename, pos, rot, size_of):
        """Функция загружает объект в графический движок."""
        self.debug("Подготовка к импорту в графический движок...")

        # Импорт из файла
        obj = OBJ(filename, self._loader, swapyz=True)

        self.debug("Модель загружена.")

        self._objects.append([obj, pos, rot, size_of, True])

        self.debug("Модель успешно импортирована в графический движок!")
    
    def load_picture(self, picture, pos, rot, size):
        """Загружает картинку."""
        self._pictures.append((picture, (-pos[0], -pos[1], pos[2]), (rot[0], -rot[1], -rot[2], rot[3]), size))
    
    def fix_orient(self, obj, pos, rot, size):
        """Функция для синхронизации объектов с PyBullet."""
        self._objects[obj][1:4] = [pos, rot, size]
    
    def set_camera_target(self, eye, center, min_dist, max_dist):
        """Задаёт позицию камеры PyOpenGL."""
        self._camera[1] = eye
        self._camera[2] = center
        self._camera[3] = self._get_up_vector((float(eye[0]), float(eye[1]), float(eye[2])), (float(center[0]), float(center[1]), float(center[2])))
        self._camera[4] = min_dist
        self._camera[5] = max_dist
    
    def import_spherical_background(self, surface):
        """Импорт текстурного заднего фона."""
        self._background = True
        self._background_texture_id = self._surface_to_opengl_texture(surface)
        self._background_sphere = self._create_sphere(100, 2048, 2048)
    
    def set_visibility(self, obj_ind, value):
        """Задаёт необходимость отрисовки конкретного объекта."""
        self._objects[obj_ind][4] = value
    
    def disable_background(self):
        """Возвращает отрисовку заднего фона по цвету."""
        self._background = None
    
    def stop(self):
        """Завершает работу графического движка."""
        pygame.quit()
    

    def _surface_to_opengl_texture(self, surface):
        """Функция для преобразования pygame.Surface в текстуру PyOpenGL."""
        texture_data = pygame.image.tostring(pygame.transform.flip(surface, True, False), "RGBA", True)
        width = surface.get_width()
        height = surface.get_height()

        # Генерация текстуры
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                    GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return texture

    def _draw_textured_panel(self, texture, position, quaternion, scale_x, scale_y):
        """Функция для отображения текстуры-картинки в PyOpenGL."""
        glScalef(-1, -1, 1)
        glPushAttrib(GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT)
        
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBindTexture(GL_TEXTURE_2D, texture)
        
        glPushMatrix()
        
        # Применение ориентации
        glTranslate(*position)
        glMultMatrixf(self.__quaternion_to_matrix(quaternion))
        glScale(scale_x, scale_y, 1.0)
        
        # Отрисовка
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex3f(-0.5, -0.5, 0)
        glTexCoord2f(1, 1); glVertex3f(0.5, -0.5, 0)
        glTexCoord2f(1, 0); glVertex3f(0.5, 0.5, 0)
        glTexCoord2f(0, 0); glVertex3f(-0.5, 0.5, 0)
        glEnd()
        
        glPopMatrix()
        glPopAttrib()

    def _render_background(self, sphere, texture_id):
        """Отрисовка текстурного заднего фона."""
        glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT)
        
        glDisable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)

        gluSphere(sphere[0], sphere[1], sphere[2], sphere[3])

        glPopAttrib()
    
    def _create_sphere(self, radius, slices, stacks):
        """Создаёт сферу для отображения текстурного заднего фона."""
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        return quadric, radius, slices, stacks
    
    def __quaternion_to_matrix(self, q):
        """Функция для получения матрицы поворота в кватернионах. Один из единственных способов получить эйлеры из кватернионов."""
        w, x, y, z = q
        n = math.sqrt(w**2 + x**2 + y**2 + z**2)
        if n < 1e-10:
            return [1.0]*16
        w /= n
        x /= n
        y /= n
        z /= n
        
        # Моделирование
        return [
            1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w),     0,
            2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w),     0,
            2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y), 0,
            0,                 0,                 0,                 1
        ]

    def _get_up_vector(self, eye, center):
        """Функция для получения корректного направления up в камере PyOpenGL."""
        direction = np.array(center) - np.array(eye)
        direction /= np.linalg.norm(direction)
        
        if np.allclose(direction, [0, 1, 0], atol=1e-3):
            return (0, 0, 1)
        else:
            return (0, 1, 0)


    def debug(self, message):
        """Функция для сообщений от класса Window."""
        global _debg
        if _debg:
            print(colored("WIN-DEBUG: " + message, 'green'))


# Решала 8)

class Reactor:
    """Главный класс. Именно он отвечает за выполнение абсолютно всех действий."""

    def __init__(self, window_size, win_name, gravity=-9.81, win_icon=None, debug=True, draw_window=True):
        """Создание Реактора."""

        global _have_space, _window, _debg

        if not _have_space:
            self._model_list = []
            self._debg = debug
            _debg = debug

            # Подключение к физическому движку.
            pybullet.connect(pybullet.DIRECT)
            pybullet.setGravity(0, 0, gravity)
            self.debug("Успешная инициализация PyBullet.")
            _have_space = True

            self.debug("Привет от Reactor! :> Пространство создано. Итерация физики происходит 60 раз в секунду!")
            self.debug("Внимание! Пути к моделям должны быть на английском языке! Русский не поддерживается :<")

            self._window = None

            if draw_window:
                # Подключение к графическому движку.
                self._window_size = window_size
                self._window = Window(window_size, win_name, win_icon)
                self.debug("Окно игры готово!")
        else:
            self.error("Reactor поддерживает только одно пространство на сессию :(")
    
    def step(self):
        """Шаг в физической симуляции и синхронизация графического и физического движков."""

        for _ in range(3):
            pybullet.stepSimulation()
        
        for obj in range(len(self._model_list)):
            self._model_list[obj].fix_orient()
            if self._window is not None:
                pos = self._model_list[obj].pos
                size = self._model_list[obj].size
                rot = self._model_list[obj].rot
                self._window.fix_orient(obj, pos, rot, size)
    
    def model(self, filename, mass, pos, rot=(1, 0, 0, 0), size=(1, 1, 1), vel=(0, 0, 0), ang_vel=(1, 0, 0, 0), lin_fr=5, lin_dp=0, ang_fr=0, ang_dp=0.9):
        """Создание объекта. Возвращает объект."""
        try:
            mdl = Model(filename, mass, self._bswap_system(pos), self._bswap_system(rot), self._bswap_system(size), self._bswap_system(vel), self._bswap_system(ang_vel), lin_fr, lin_dp, ang_fr, ang_dp)
            if self._window is not None:
                self._window.load_model(filename, pos, rot, size)
            self.debug("Успешно создана модель: " + filename)
            self._model_list.append(mdl)
            return mdl
        except FileNotFoundError as e:
            self.error(e)
            self.error("Файл не найден! Проверьте, находится ли текстура, .mtl и .obj файлы в одной директории. Путь директории на английском?")
            self.error("Ошибка в симуляции :< Дальнейшая работа может быть некорректной! При неудачном импорте возвращается None, следует отлавливать!")
        except Exception as e:
            self.error(e)
            self.error("Непредвиденная ошибка!")
            self.error("Ошибка в симуляции :< Дальнейшая работа может быть некорректной! При неудачном импорте возвращается None, следует отлавливать!")

    def render(self):
        """Перенаправляет на функцию render() класса Window."""
        if self._window is not None:
            return self._window.render()

    def apply_surface(self, surface):
        """Применяет экран к графическому окну."""
        if self._window is not None:
            self._window._surface.blit(surface, (0, 0))
    
    def set_bgcolor(self, color):
        """Задаёт цвет заднего фона графического движка."""
        if self._window is not None:
            glClearColor(color[0] / 255, color[1] / 255, color[2] / 255, 1.0)
            self._window._background_color = color
    
    def set_camera_target(self, pos, center, min_dist=0.1, max_dist=100):
        """Задаёт цель камеры графического движка."""
        if self._window is not None:
            self._window.set_camera_target(pos, center, min_dist, max_dist)

    def set_camera(self, pos, y_angle, up_angle, min_dist=0.1, max_dist=100):
        """Задаёт ориентацию камеры графического движка."""
        if self._window is not None:
            center = list(self._angle_to_vector(y_angle, up_angle))
            for i in range(3):
                center[i] += pos[i]
            self._window.set_camera_target(pos, center, min_dist, max_dist)

    def destroy(self, obj):
        """Уничтожает объект."""
        try:
            if obj is Model:
                pybullet.removeBody(obj._body_ind)
                if self._window is not None:
                    del self._window._objects[self._model_list.index(obj)]
                del self._model_list[self._model_list.index(obj)]
                self.debug("Модель успешно удалена.")
            elif obj is Fixed_joint:
                pybullet.removeBody(obj._joint_index)
                self.debug("Фиксированное соединение успешно удалено.")
            else:
                self.error("Это не объект класса Model!")
        except Exception:
            self.error("Объект уже удалён!")
    
    def pos_to_global(self, rel_target, rel_orient, self_orient=((0, 0, 0), (1, 0, 0, 0))):
        """Преобразует трёхуровневые координаты в глобальные."""
        res = self._get_3level((self._bswap_system(rel_target[0]), self._bswap_system(rel_target[1])), (self._bswap_system(rel_orient[0]), self._bswap_system(rel_orient[1])), (self._bswap_system(self_orient[0]), self._bswap_system(self_orient[1])))
        return (self._swap_system(res[0]), self._swap_system(res[1]))

    def global_to_relative(self, fpos, frot, spos, srot):
        """Глобальная позиция в относительную."""
        inv_pos_F, inv_orn_F = pybullet.invertTransform(fpos, frot)
        relative_pos, relative_orn = pybullet.multiplyTransforms(inv_pos_F, inv_orn_F, spos, srot)
        return (relative_pos, relative_orn)
    
    def picture(self, surface, pos, rot=(1, 0, 0, 0), size=(1, 1)):
        """Импорт картинки в графический движок."""
        if self._window is not None:
            self._window.load_picture(surface, pos, rot, size)
    
    def euler_quat(self, euler_xyz):
        """Из Эйлера (радианы) в кватернионы."""
        return self._swap_system(pybullet.getQuaternionFromEuler(self._bswap_system(euler_xyz)))
    
    def set_background(self, surface):
        """Задаёт текстурный задний фон."""
        if self._window is not None:
            self._window.import_spherical_background(surface)
    
    def enable_color_background(self):
        """Возвращает задний фон по цвету."""
        if self._window is not None:
            self._window.disable_background()
    
    def impulse(self, obj, vector, global_point):
        """Применяет импульс к объекту."""
        pybullet.applyExternalForce(
            objectUniqueId=obj.body_ind,
            linkIndex=-1,
            forceObj=vector,
            posObj=global_point,
            flags=pybullet.WORLD_FRAME
        )
    
    def change_visibility(self, obj, is_visible):
        """Задаёт видимость определённого объекта в графическом движке."""
        if self._window is not None:
            self._window.set_visibility(self._model_list.index(obj), is_visible)
    
    def vector_to_angle(self, x, y, z):
        """Вектор в двойной угол."""
        res = self._decart_to_polar_3D((x, -y, z))
        return (res[0], res[1])
    
    def two_axed(self, angle_x, angle_y, angle_z, angle_w):
        """Переход из трёхмерного поворота в двойной."""
        res = self._quat_to_vector((angle_x, angle_y, angle_z, angle_w))
        result = self._decart_to_polar_3D(res)
        return result
    
    def fixed_joint(self, body1, body2, body1_relpos, body2_relpos, body1_relor, body2_relor):
        """Создаёт фиксированное соединение."""
        jnt = Fixed_joint(body1._body_ind, body2._body_ind, self._bswap_system(body1_relpos), self._bswap_system(body2_relpos), self._bswap_system(body1_relor), self._bswap_system(body2_relor))
        self.debug("Фиксированное соединение успешно создано!")
        return jnt
    
    def check_collision(self, obj1, obj2):
        """Проверяет коллизию."""
        return pybullet.getClosestPoints(obj1._body_ind, obj2._body_ind, 0.0)
    
    def point_inside(self, obj, point_pos):
        """Проверяет, находится ли точка внутри объекта."""
        point = self._swap_system(point_pos)
        temp_collision = pybullet.createCollisionShape(pybullet.GEOM_SPHERE, radius=0.0)
        temp_body = pybullet.createMultiBody(
            baseMass=0, 
            baseCollisionShapeIndex=temp_collision, 
            basePosition=point
        )

        contacts = pybullet.getClosestPoints(temp_body, obj._body_ind, 0.0)

        pybullet.removeBody(temp_body)
        
        return contacts
    
    def shutdown(self):
        """Завершение работы."""
        pybullet.disconnect()
        if self._window is not None:
            self._window.stop()
        self.debug("Reactor завершил работу.")
    
    def frame_size(self, distance):
        """Считает размер картинки во весь экран по дистанции от камеры."""
        return (distance * 2 * (self._window_size[0] / self._window_size[1]), distance * 2)
    
    
    def _swap_system(self, data):
        """Переходит из ориентационной системы PyBullet (позиция x, z, y; поворот x, z, y, w) в PyOpenCV (x y z; w x y z)."""
        if len(data) == 3:
            return (data[0], data[2], data[1])
        else:
            return (data[3], data[0], data[2], data[1])
    
    def _bswap_system(self, data):
        """Обратно функции _swap_system()."""
        if len(data) == 3:
            return (data[0], data[2], data[1])
        else:
            return (data[1], data[3], data[2], data[0])
    
    def _get_3level(self, r_pos_rot, r_pos_rot_trgt, s_pos_rot):
        """Преобразует трёхуровневые координаты в глобальные на низком уровне."""
        from_self_to_rel = self.__relative_to_global(r_pos_rot[0], r_pos_rot[1], s_pos_rot[0], s_pos_rot[1])
        from_rel_to_global = self.__relative_to_global(from_self_to_rel[0], from_self_to_rel[1], r_pos_rot_trgt[0], r_pos_rot_trgt[1])
        res = (from_rel_to_global[0], from_rel_to_global[1])
        return res
    
    def __relative_to_global(self, fpos, frot, spos, srot):
        """Преобразует относительные координаты в глобальные."""
        global_pos, global_orn = pybullet.multiplyTransforms(fpos, frot, spos, srot)
        return (global_pos, global_orn)
    
    def _quat_to_vector(self, q):
        """Кватернионы в вектор."""
        rotated_vector = pybullet.rotateVector((q[0], -q[1], q[2], q[3]), (0, 0, 1))
        return self._swap_system(np.array(rotated_vector))
    
    def _decart_to_polar_3D(self, pos):
        """3D-Декартовые координаты в Полярные."""
        res_1 = self.__decart_to_polar((pos[0], pos[2]))
        angle_1 = res_1[0]
        res_2 = self.__decart_to_polar((res_1[1], pos[1]))
        angle_2 = res_2[0]
        root = res_2[1]
        return (angle_1, angle_2, root)

    def __polar_to_decart_3D(self, ang_1, ang_2, gip):
        """Преобразует 3D-Полярную систему координат в 3D-Декартовую."""
        first_gip, y = self.___polar_to_decart(ang_2, gip)
        x, z = self.___polar_to_decart(ang_1, first_gip)
        return (x, y, z)
    
    def _angle_to_vector(self, y_angle, up_angle):
        """Преобразует двойной поворот в вектор."""
        fangle = y_angle - y_angle // 360 * 360
        sangle = up_angle - up_angle // 360 * 360
        res = self.__polar_to_decart_3D(fangle, sangle, 10)
        result = (res[0], -res[1], res[2])
        return result

    def __decart_to_polar(self, pos):
        """Декартовые координаты в Полярные."""
        x = pos[0]
        y = pos[1]
        complex_format = x + 1j * y
        res = [float(np.abs(complex_format)), float(np.angle(complex_format, deg = True)) + 90]
        if res[1] < 0:
            res[1] += 360
        return (res[1], res[0])

    def ___polar_to_decart(self, ang, gip):
        """Переход из Полярной системы координат в Декартовую."""
        angle = ang - ang // 360 * 360 - 90
        if angle == -90:
            return (0, -gip)
        elif angle == 0:
            return (gip, 0)
        elif angle == 90:
            return (0, gip)
        elif angle == 180:
            return (-gip, 0)
        x = gip * math.cos(math.radians(angle))
        y = gip * math.sin(math.radians(angle))
        return (x, y)

    
    def debug(self, message):
        """Сообщения от класса Reactor()."""
        if self._debg:
            print(colored("DEBUG: " + message, 'green'))

    def error(self, message):
        """Ошибки от класса Reactor()."""
        if self._debg:
            print(colored("ERROR: " + message, 'red'))
    
    def thanks(self):
        """❤️"""
        print(colored("Спасибочки большое за помощь в разработке! ❤️\n\n💻 Разработчик: Манеев Егор Михайлович (☕️ Kruzhka Games, https://github.com/KruzhkaGames)\n\n🎨 Помощь в разработке графического движка: Петрыкина Ирина Романовна (🗻 Pirenoid, https://github.com/Pirenoid)", 'cyan'))


# Моделька :>

class Model:
    """Класс объекта-модели."""

    def __init__(self, filename, mass, pos, rot, size, vel, ang_vel, lin_fr, lin_dp, ang_fr, ang_dp):
        """Создаёт объект в физическом движке."""

        self._visual_ind = pybullet.createVisualShape(
            shapeType=pybullet.GEOM_MESH,
            fileName=filename,
            rgbaColor=[1, 1, 1, 1],
            specularColor=[0.4, 0.4, 0],
            visualFramePosition=[0, 0, 0],
            meshScale=size)

        self.debug("Подготовлена текстура модели.")

        self._collision_ind = pybullet.createCollisionShape(
            shapeType=pybullet.GEOM_MESH,
            fileName=filename,
            collisionFramePosition=[0, 0, 0],
            meshScale=size)

        self.debug("Подготовлена физика модели.")
            
        self._body_ind = pybullet.createMultiBody(
            baseMass=mass,
            baseCollisionShapeIndex=self._collision_ind,
            baseVisualShapeIndex=self._visual_ind,
            basePosition=pos,
            useMaximalCoordinates=True)

        pybullet.resetBasePositionAndOrientation(self._body_ind, pos, rot)
        pybullet.resetBaseVelocity(self._body_ind, linearVelocity=vel, angularVelocity=ang_vel)
        pybullet.changeDynamics(self._body_ind, linkIndex=-1, lateralFriction=lin_fr, linearDamping=lin_dp, spinningFriction=ang_fr, rollingFriction=ang_fr, angularDamping=ang_dp)

        # Задаём параметры.
        self.pos, self.rel_pos, self.rel_pos_trgt, self.self_pos = self._swap_system(pos), (0, 0, 0), None, (0, 0, 0)
        self.rot, self.rel_rot, self.rel_rot_trgt, self.self_rot = self._swap_system(rot), (1, 0, 0, 0), None, (1, 0, 0, 0)
        self.size = self._swap_system(size)
        self.vel, self.ang_vel = self._swap_system(vel), self._swap_system(ang_vel)

        self.debug("Модель успешно импортирована в физический движок!")


    def fix_orient(self):
        """Обновление параметров ориентации."""
        self.pos, self.rot = pybullet.getBasePositionAndOrientation(self._body_ind)
        self.pos, self.rot = self._swap_system(self.pos), self._swap_system(self.rot)
        self.rel_pos, self.rel_rot, self.rel_pos_trgt, self.rel_rot_trgt, self.self_pos, self.self_rot = (0, 0, 0), (1, 0, 0, 0), None, None, (0, 0, 0), (1, 0, 0, 0)
        self.vel, self.ang_vel = pybullet.getBaseVelocity(self._body_ind)
        self.vel, self.ang_vel = self._swap_system(self.vel), self._swap_system(self.ang_vel)

    
    def set_pos(self, position):
        """Задаёт глобальную позицию."""
        pybullet.resetBasePositionAndOrientation(self._body_ind, self._bswap_system(position), self._bswap_system(self.rot))
        self.pos, self.rel_pos, self.rel_pos_trgt, self.self_pos = position, (0, 0, 0), None, (0, 0, 0)
    
    def set_rel_orient(self, position, rotation, target):
        """Задаёт ориентацию относительно точки."""
        self.rel_pos_trgt = target[0]
        self.rel_rot_trgt = target[1]
        self.rel_pos = position
        self.rel_rot = rotation
        self.self_pos = (0, 0, 0)
        self.self_rot = (1, 0, 0, 0)
        gl_pos = self._get_3level((self._bswap_system(self.rel_pos_trgt), self._bswap_system(self.rel_rot_trgt)), (self._bswap_system(self.rel_pos), self._bswap_system(self.rel_rot)), (self._bswap_system(self.self_pos), self._bswap_system(self.self_rot)))
        self.pos, self.rot = self._swap_system(gl_pos[0]), self._swap_system(gl_pos[1])
        pybullet.resetBasePositionAndOrientation(self._body_ind, gl_pos[0], gl_pos[1])
    
    def set_self_orient(self, position, rotation):
        """Задаёт собственную ориентацию."""
        self.self_pos = position
        self.self_rot = rotation
        gl_pos = self._get_3level((self._bswap_system(self.rel_pos_trgt), self._bswap_system(self.rel_rot_trgt)), (self._bswap_system(self.rel_pos), self._bswap_system(self.rel_rot)), (self._bswap_system(self.self_pos), self._bswap_system(self.self_rot)))
        self.pos, self.rot = self._swap_system(gl_pos[0]), self._swap_system(gl_pos[1])
        pybullet.resetBasePositionAndOrientation(self._body_ind, gl_pos[0], gl_pos[1])
    

    def _get_3level(self, r_pos_rot, r_pos_rot_trgt, s_pos_rot):
        """Преобразует трёхуровневую ориентацию в глобальную позицию."""
        from_self_to_rel = self.__relative_to_global(r_pos_rot[0], r_pos_rot[1], s_pos_rot[0], s_pos_rot[1])
        from_rel_to_global = self.__relative_to_global(from_self_to_rel[0], from_self_to_rel[1], r_pos_rot_trgt[0], r_pos_rot_trgt[1])
        res = (from_rel_to_global[0], from_rel_to_global[1])
        return res

    def __relative_to_global(self, fpos, frot, spos, srot):
        """Относительная позиция в глобальную."""
        global_pos, global_orn = pybullet.multiplyTransforms(fpos, frot, spos, srot)
        return (global_pos, global_orn)
    
    
    def set_rot(self, rotation):
        """Поворачивает объект."""
        pybullet.resetBasePositionAndOrientation(self._body_ind, self._bswap_system(self.pos), self._bswap_system(rotation))
        self.rot, self.rel_rot, self.rel_rot_trgt, self.self_rot = rotation, (1, 0, 0, 0), None, (1, 0, 0, 0)
    

    def set_vel(self, velocity):
        """Задаёт линейную скорость."""
        pybullet.resetBaseVelocity(self._body_ind, linearVelocity=self._bswap_system(velocity))
        self.vel = velocity

    def set_ang_vel(self, velocity):
        """Задаёт угловую скорость."""
        pybullet.resetBaseVelocity(self._body_ind, angularVelocity=self._bswap_system(velocity))
        self.ang_vel = velocity

    def debug(self, message):
        """Сообщения от класса Model."""
        global _debg
        if _debg:
            print(colored("MDL-DEBUG: " + message, 'green'))
    
    def _swap_system(self, data):
        """Переход из координатной системы PyBullet в PyOpenGL."""
        if len(data) == 3:
            return (data[0], data[2], data[1])
        else:
            return (data[3], data[0], data[2], data[1])
    
    def _bswap_system(self, data):
        """Обратная функции _swap_system()."""
        if len(data) == 3:
            return (data[0], data[2], data[1])
        else:
            return (data[1], data[3], data[2], data[0])

class Fixed_joint:
    """Класс фиксированного соединения."""

    def __init__(self, body1, body2, body1_relpos, body2_relpos, body1_relor, body2_relor):
        """Создаёт соединение в физическом движке."""
        self._joint_index = pybullet.createConstraint(
            parentBodyUniqueId=body1,
            childBodyUniqueId=body2,
            parentLinkIndex=-1,
            childLinkIndex=-1,
            jointType=pybullet.JOINT_FIXED,
            jointAxis=[0, 0, 0],
            parentFramePosition=body1_relpos,
            childFramePosition=body2_relpos,
            parentFrameOrientation=body1_relor,
            childFrameOrientation=body2_relor
        )
