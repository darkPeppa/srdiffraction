import matplotlib.pyplot as plt
import numpy as np

# 1. Загрузка данных из файла (разделитель табуляция)
#Бериллий
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Be 1000000 events.txt', delimiter='\t', skiprows=1)
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Be 1000000 events nonzero.txt', delimiter='\t', skiprows=1)

#Титан
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Ti 1000000 events.txt', delimiter='\t', skiprows=1)
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Ti 1000000 events nonzero.txt', delimiter='\t', skiprows=1)

#Лейкосапфир
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Al2O3 1000000 events.txt', delimiter='\t', skiprows=1)
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\Al2O3 1000000 events nonzero.txt', delimiter='\t', skiprows=1)

#Стеклоуглерод
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\C 1000000 events.txt', delimiter='\t', skiprows=1)
#data = np.loadtxt(r'C:\Users\chiza\Documents\G4beamlineExamples\Diffraction\C 1000000 events nonzero.txt', delimiter='\t', skiprows=1)

data = np.loadtxt(r'C:\Users\chiza\Documents\GitHub\srdiffraction\build\energy_deposition_pmma_nt_Edep_table.txt', delimiter='\t', skiprows=1)



# Предполагаем, что в файле три колонки: x, y, z
x = data[:, 0]
y = data[:, 1]
z = data[:, 2]

# 2. Построение scatter-графика с цветовой кодировкой
plt.figure(figsize=(8, 6))
sc = plt.scatter(x, y, c=z, cmap='viridis', s=1, alpha=0.8)

# 3. Добавление цветовой шкалы
cbar = plt.colorbar(sc)
cbar.set_label('Поглощенная энергия, МэВ')

# 4. Оформление
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Распределение поглощенной энергии по площади')
#plt.title('Распределение поглощенной энергии по площади (Edep !=0)')
plt.grid(True, linestyle='--', alpha=0.5)
plt.axis('equal')  # нужен одинаковый масштаб осей

# 5. Центрирование относительно (0,0)
max_abs = max(np.abs(x).max(), np.abs(y).max())
plt.xlim(-max_abs, max_abs)
plt.ylim(-max_abs, max_abs)

plt.show()