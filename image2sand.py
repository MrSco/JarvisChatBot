import cv2
import math
from queue import PriorityQueue


class Image2Sand:
    """
    Image2Sand - Convert images to sand table coordinates

    This class processes images and converts them to polar coordinates
    according to the specified settings, supporting multiple output formats including:
     Default: HackPack Sand Garden .ino in this repository
     theta-rho format: for use with sand tables like Sisyphus and Dune Weaver Mini.

    Note:
     For Dune Weaver Mini compatibility, this class uses continuous theta values
     that can exceed 2π (360 degrees). This allows the arm to make multiple revolutions
     without creating unintended circles in the patterns.
    """

    def __init__(self):
        self.ordered_contours_save = []
    
    def process_image(self, image_input, options=None):
        """Process an image and generate coordinates.
        
        Args:
            image_input: Either a string path to an image file or a numpy array containing the image
            options: Dictionary of processing options
                epsilon: Controls point density (0.1-5.0)
                contour_mode: 'Tree' or 'External'
                is_loop: Whether to close the path as a loop
                minimize_jumps: Try to find optimal paths between disconnected contours
                output_format: 0=Default, 1=Single Byte, 2=.thr, 3=Whitespace
                max_points: Maximum number of points to generate
        
        Returns:
            Dictionary containing:
                polar_points: List of polar coordinates
                formatted_coords: Formatted string output
                point_count: Number of points generated
        
        Raises:
            ValueError: If the image cannot be loaded or is invalid
        """
        # Set default options if not provided
        if options is None:
            options = {
                'epsilon': 0.5,
                'contour_mode': 'Tree',
                'is_loop': True,
                'minimize_jumps': True,
                'output_format': 2,
                'max_points': 300
            }
        
        # Handle different input types
        if isinstance(image_input, str):
            # Load image from file path
            img = cv2.imread(image_input)
            if img is None:
                raise ValueError(f"Could not load image: {image_input}")
        else:
            # Assume input is already an image array
            img = image_input
            if img is None or not hasattr(img, 'shape') or len(img.shape) < 2:
                raise ValueError("Invalid image input: must be a valid image array")
        
        # Convert to grayscale if image is in color
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150, 3)
        
        # Add morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel)
        edges = cv2.erode(edges, kernel)
        
        # Invert colors
        edges = cv2.bitwise_not(edges)
        
        # Process the edges to generate dots
        return self.generate_dots(edges, options)
    
    def generate_dots(self, edge_image, options):
        """Generates dots from the edge image"""
        epsilon = options.get('epsilon', 0.5)
        contour_mode = options.get('contour_mode', 'Tree')
        is_loop = options.get('is_loop', True)
        minimize_jumps = options.get('minimize_jumps', True)
        output_format = options.get('output_format', 0)
        max_points = options.get('max_points', 300)
        
        retrieval_mode = cv2.RETR_TREE if contour_mode == 'Tree' else cv2.RETR_EXTERNAL
        
        # Get ordered contours
        ordered_contours = self.get_ordered_contours(edge_image, epsilon, retrieval_mode, max_points)
        
        # Trace contours
        traced_contours = self.trace_contours(ordered_contours, is_loop, minimize_jumps)
        
        # Save for future reference
        self.ordered_contours_save = traced_contours
        
        # Process contours based on output format
        if output_format == 2:  # .thr format
            processed_contours = [self.add_interpolated_points(contour, epsilon) for contour in traced_contours]
        else:
            processed_contours = traced_contours
        
        # Flatten contours to a single list of points
        ordered_points = [point for contour in processed_contours for point in contour]
        
        # If the path forms a loop or should be closed
        if self.is_fully_closed(ordered_points) or is_loop:
            ordered_points = self.reorder_points_for_loop(ordered_points)
        
        # Remove consecutive duplicates
        ordered_points = self.remove_consecutive_duplicates(ordered_points)
        
        # For final output - if last point is same as first point, drop it
        if self.is_fully_closed(ordered_points):
            ordered_points = ordered_points[:-1]
        
        # Convert to polar coordinates
        polar_points = self.calculate_polar_coordinates(ordered_points)
        
        # Format the coordinates based on output type
        formatted_coords = self.format_coordinates(polar_points, output_format)
        
        return {
            'polar_points': polar_points,
            'formatted_coords': formatted_coords,
            'point_count': len(ordered_points)
        }
    
    def format_coordinates(self, polar_points, output_format):
        """Format polar coordinates according to the specified output format"""
        if output_format == 0:  # Default
            # For Image2Sand.ino code, normalize the theta values
            formatted = []
            for p in polar_points:
                normalized_theta = ((p['theta'] % 3600) + 3600) % 3600  # Ensure positive value between 0-3600
                # Use string concatenation to avoid f-string escaping issues
                formatted.append("{" + f"{int(p['r'])},{int(normalized_theta)}" + "}")
            return ','.join(formatted)
        
        elif output_format == 1:  # Single Byte
            formatted = []
            for p in polar_points:
                normalized_theta = ((p['theta'] % 3600) + 3600) % 3600
                # Use string concatenation to avoid f-string escaping issues
                formatted.append("{" + f"{round(255 * p['r'] / 1000)},{round(255 * normalized_theta / 3600)}" + "}")
            return ','.join(formatted)
        
        elif output_format == 2:  # .thr
            # For .thr format, keep continuous theta values
            # Convert from tenths of degrees back to radians
            # Apply a 90° clockwise rotation by subtracting π/2 (900 in tenths of degrees) from theta
            formatted = []
            for p in polar_points:
                rotated_theta = p['theta'] - 900
                formatted.append(f"{(-rotated_theta * math.pi / 1800):.5f} {(p['r'] / 1000):.5f}")
            return '\n'.join(formatted)
        
        elif output_format == 3:  # whitespace
            formatted = []
            for p in polar_points:
                normalized_theta = ((p['theta'] % 3600) + 3600) % 3600
                r_binary = format(round(255 * p['r'] / 1000), '08b').replace('0', ' ').replace('1', '\t')
                theta_binary = format(round(255 * normalized_theta / 3600), '08b').replace('0', ' ').replace('1', '\t')
                formatted.append(f"{r_binary}{theta_binary}")
            return '\n'.join(formatted)
        
        return ""
    
    def calculate_polar_coordinates(self, points):
        """Calculate polar coordinates from Cartesian points"""
        # Find the center for the polar conversion
        center = self.find_maximal_center(points)
        
        # Adjust points relative to center
        centered_points = [{'x': p['x'] - center['centerX'], 'y': p['y'] - center['centerY']} for p in points]
        
        # Calculate maximum radius for normalization
        max_radius = max(math.sqrt(p['x']**2 + p['y']**2) for p in centered_points)
        
        # Calculate initial angles for all points
        polar_points = []
        for p in centered_points:
            r = math.sqrt(p['x']**2 + p['y']**2)
            # Get the basic angle in radians
            theta = math.atan2(p['y'], p['x'])
            
            # Adjust theta to align 0 degrees to the right and 90 degrees up by flipping the y-axis
            theta = -theta
            
            polar_points.append({
                'r': r * (1000 / max_radius),
                'theta': theta,  # Store in radians initially
                'x': p['x'],
                'y': p['y']
            })
        
        # Process points to create continuous theta values
        for i in range(1, len(polar_points)):
            prev = polar_points[i-1]
            curr = polar_points[i]
            
            # Calculate the difference between current and previous theta
            diff = curr['theta'] - prev['theta']
            
            # If the difference is greater than π, it means we've wrapped around counterclockwise
            # Adjust by subtracting 2π
            if diff > math.pi:
                curr['theta'] -= 2 * math.pi
            # If the difference is less than -π, it means we've wrapped around clockwise
            # Adjust by adding 2π
            elif diff < -math.pi:
                curr['theta'] += 2 * math.pi
        
        # Convert to degrees * 10 for the final format
        for p in polar_points:
            p['theta'] = p['theta'] * (1800 / math.pi)  # Convert radians to tenths of degrees
        
        return polar_points
    
    def get_ordered_contours(self, edge_image, initial_epsilon, retrieval_mode, max_points):
        """Get ordered contours from the edge image"""
        contours, hierarchy = cv2.findContours(cv2.bitwise_not(edge_image), retrieval_mode, cv2.CHAIN_APPROX_SIMPLE)
        
        # Deduplicate contours
        unique_contours = self.deduplicate_contours(contours)
        
        max_iterations = 100  # Maximum iterations to avoid infinite loop
        
        contour_points = []
        total_points = 0
        epsilon = initial_epsilon
        iterations = 0
        
        while iterations < max_iterations:
            total_points = 0
            contour_points = []
            
            for contour in unique_contours:
                simplified = cv2.approxPolyDP(contour, epsilon, True)
                
                points = []
                for i in range(len(simplified)):
                    point = simplified[i][0]
                    points.append({'x': int(point[0]), 'y': int(point[1])})
                
                if points:  # Check for empty contours
                    if self.is_nearly_closed(contour):  # Only close the contour if it's nearly closed
                        points = self.close_contour(points)
                    
                    if self.is_fully_closed(points):
                        # Move starting point to nearest the center
                        points = self.reorder_points_for_loop(points)
                    
                    contour_points.append(points)
                    total_points += len(points)
            
            if total_points <= max_points:
                break
            
            # Adjust epsilon to reduce points
            points_over = total_points - max_points
            epsilon = self.adjust_epsilon(epsilon, points_over)
            iterations += 1
        
        if total_points > max_points and iterations >= max_iterations:
            flattened_points = [point for sublist in contour_points for point in sublist]
            contour_points = [flattened_points[:max_points]]  # Take the first N points
        
        if not contour_points:
            raise ValueError("No valid contours found.")
        
        # Calculate distances and find the best path
        distances = self.calculate_distances(contour_points)
        path = self.tsp_nearest_neighbor(distances, contour_points)
        ordered_contours = self.reorder_contours(contour_points, path)
        
        return ordered_contours
    
    def adjust_epsilon(self, epsilon, points_over):
        """Adjust epsilon based on how many points we're over the target"""
        if points_over > 100:
            return epsilon + 0.5
        elif points_over <= 20:
            return epsilon + 0.1
        else:
            # Scale adjustment for points over the target between 20 and 100
            scale = (points_over - 20) / (100 - 20)  # Normalized to range 0-1
            return epsilon + 0.1 + 0.5 * scale  # Adjust between 0.1 and 0.5
    
    def is_nearly_closed(self, contour, percent_threshold=0.1):
        """Checks if a contour is nearly closed"""
        # Get the bounding box of the contour
        x, y, w, h = cv2.boundingRect(contour)
        size = math.sqrt(w * w + h * h)
        
        # Calculate the distance between the first and last points
        start_point = {'x': contour[0][0][0], 'y': contour[0][0][1]}
        end_point = {'x': contour[-1][0][0], 'y': contour[-1][0][1]}
        distance = math.sqrt((start_point['x'] - end_point['x']) ** 2 + (start_point['y'] - end_point['y']) ** 2)
        
        # Use a threshold based on the size of the object
        threshold = size * percent_threshold
        return distance < threshold
    
    def is_contour_closed(self, contour):
        """Check if contour is fully closed"""
        start_point = {'x': contour[0][0][0], 'y': contour[0][0][1]}
        end_point = {'x': contour[-1][0][0], 'y': contour[-1][0][1]}
        
        return start_point == end_point
    
    def is_fully_closed(self, points):
        """Checks if a PointList has the same first and last point"""
        if not points:
            return False
        return points[0]['x'] == points[-1]['x'] and points[0]['y'] == points[-1]['y']
    
    def close_contour(self, points):
        """Closes a contour by adding the first point at the end"""
        if len(points) > 1 and (points[0]['x'] != points[-1]['x'] or points[0]['y'] != points[-1]['y']):
            points.append({'x': points[0]['x'], 'y': points[0]['y']})
        return points
    
    def are_contours_similar(self, contour1, contour2, similarity_threshold):
        """Determine if two contours are similar based on bounding box overlap"""
        # Calculate the bounding boxes of the contours
        x1, y1, w1, h1 = cv2.boundingRect(contour1)
        x2, y2, w2, h2 = cv2.boundingRect(contour2)
        
        # Calculate the intersection of the bounding boxes
        x_intersect = max(x1, x2)
        y_intersect = max(y1, y2)
        w_intersect = min(x1 + w1, x2 + w2) - x_intersect
        h_intersect = min(y1 + h1, y2 + h2) - y_intersect
        
        # Check if there is an intersection
        if w_intersect <= 0 or h_intersect <= 0:
            return False
        
        intersection_area = w_intersect * h_intersect
        
        # Calculate the union of the bounding boxes
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - intersection_area
        
        # Calculate the similarity based on the intersection over union (IoU)
        similarity = intersection_area / union_area
        
        return similarity > similarity_threshold
    
    def deduplicate_contours(self, contours, similarity_threshold=0.5):
        """Remove similar contours based on bounding box similarity"""
        unique_contours = []
        for i in range(len(contours)):
            contour = contours[i]
            is_duplicate = False
            for unique_contour in unique_contours:
                if self.are_contours_similar(contour, unique_contour, similarity_threshold):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_contours.append(contour)
        return unique_contours
    
    def interpolate_points(self, start_point, end_point, num_points):
        """Interpolate points along a straight line"""
        if num_points <= 2:
            return [start_point, end_point]
        
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            x = start_point['x'] + t * (end_point['x'] - start_point['x'])
            y = start_point['y'] + t * (end_point['y'] - start_point['y'])
            points.append({'x': x, 'y': y})
        return points
    
    def distance_between_points(self, p1, p2):
        """Calculate the distance between two points"""
        return math.sqrt((p2['x'] - p1['x']) ** 2 + (p2['y'] - p1['y']) ** 2)
    
    def add_interpolated_points(self, points, epsilon):
        """Add interpolated points to a contour based on segment length"""
        if len(points) <= 1:
            return points
        
        result = []
        for i in range(len(points) - 1):
            start_point = points[i]
            end_point = points[i + 1]
            
            # Calculate distance between points
            distance = self.distance_between_points(start_point, end_point)
            
            # Determine how many points to add based on distance and epsilon
            # For longer segments and smaller epsilon values, we want more points
            # The smaller the epsilon, the more detailed the contour, so we add more points
            points_to_add = max(2, math.ceil(distance / (epsilon * 5)))
            
            # Add interpolated points for this segment
            interpolated = self.interpolate_points(start_point, end_point, points_to_add)
            
            # Add all points except the last one (to avoid duplicates)
            if i < len(points) - 2:
                result.extend(interpolated[:-1])
            else:
                # For the last segment, include the end point
                result.extend(interpolated)
        
        return result
    
    def calculate_distances(self, contours):
        """Calculate distances between contours"""
        distances = [[] for _ in range(len(contours))]
        
        for i in range(len(contours)):
            distances[i] = [0] * len(contours)
            for j in range(len(contours)):
                if i != j:
                    start_to_start = math.hypot(
                        contours[i][0]['x'] - contours[j][0]['x'],
                        contours[i][0]['y'] - contours[j][0]['y']
                    )
                    start_to_end = math.hypot(
                        contours[i][0]['x'] - contours[j][-1]['x'],
                        contours[i][0]['y'] - contours[j][-1]['y']
                    )
                    end_to_start = math.hypot(
                        contours[i][-1]['x'] - contours[j][0]['x'],
                        contours[i][-1]['y'] - contours[j][0]['y']
                    )
                    end_to_end = math.hypot(
                        contours[i][-1]['x'] - contours[j][-1]['x'],
                        contours[i][-1]['y'] - contours[j][-1]['y']
                    )
                    distances[i][j] = min(start_to_start, start_to_end, end_to_start, end_to_end)
        
        return distances
    
    def tsp_nearest_neighbor(self, distances, contours):
        """Traveling Salesman Problem solution using Nearest Neighbor approach"""
        path = [0]
        visited = {0}
        
        while len(path) < len(contours):
            last = path[-1]
            nearest = -1
            nearest_distance = float('inf')
            
            for i in range(len(contours)):
                if i not in visited and distances[last][i] < nearest_distance:
                    nearest_distance = distances[last][i]
                    nearest = i
            
            if nearest != -1:
                path.append(nearest)
                visited.add(nearest)
        
        return path
    
    def reorder_contours(self, contours, path):
        """Reorder contours based on the path, optimizing direction for minimum distance"""
        ordered_contours = []
        
        for i in range(len(path)):
            contour_index = path[i]
            contour = contours[contour_index].copy()
            
            # Determine the direction to use the contour
            if i > 0:
                prev_contour = ordered_contours[-1]
                prev_point = prev_contour[-1]
                
                if self.is_fully_closed(contour):
                    # Contour is fully closed, so can move the startPoint
                    contour = self.reorder_points_for_loop(contour, prev_point)
                elif prev_point and contour[0]:
                    # Contour not fully closed, decide whether to reverse contour
                    start_to_start = math.hypot(
                        prev_point['x'] - contour[0]['x'],
                        prev_point['y'] - contour[0]['y']
                    )
                    start_to_end = math.hypot(
                        prev_point['x'] - contour[-1]['x'],
                        prev_point['y'] - contour[-1]['y']
                    )
                    
                    if start_to_end < start_to_start:
                        contour.reverse()
                else:
                    # Skip if any point is undefined
                    continue
            
            ordered_contours.append(contour)
        
        return ordered_contours
    
    def find_closest_point(self, contours, point):
        """Find the closest point in the contours to the given point"""
        min_distance = float('inf')
        closest_point = None
        
        for contour in contours:
            for pt in contour:
                distance = math.hypot(point['x'] - pt['x'], point['y'] - pt['y'])
                if distance < min_distance:
                    min_distance = distance
                    closest_point = pt
        
        return closest_point
    
    def create_graph_with_connection_types(self, contours):
        """Create a graph with connection types for path finding"""
        graph = []
        node_map = {}  # Dictionary to map coordinates to node index
        MAX_JUMP_CONNECTIONS = 10  # Limit the number of jump connections per node
        
        # Create nodes for each point in the contours
        for contour in contours:
            for pt in contour:
                key = f"{pt['x']},{pt['y']}"
                if key not in node_map:
                    node = {'x': pt['x'], 'y': pt['y'], 'neighbors': []}
                    graph.append(node)
                    node_map[key] = len(graph) - 1
        
        # Connect points within the same contour (regular path connections)
        for contour in contours:
            for i in range(len(contour)):
                key = f"{contour[i]['x']},{contour[i]['y']}"
                node_idx = node_map.get(key)
                node = graph[node_idx]
                
                if i > 0:
                    prev_key = f"{contour[i-1]['x']},{contour[i-1]['y']}"
                    prev_idx = node_map.get(prev_key)
                    prev_node = graph[prev_idx]
                    
                    # Check if connection already exists
                    if not any(n.get('node_idx') == prev_idx for n in node['neighbors']):
                        node['neighbors'].append({'node_idx': prev_idx, 'is_jump': False})
                        prev_node['neighbors'].append({'node_idx': node_idx, 'is_jump': False})
        
        # Create a spatial index for efficient nearest neighbor search
        spatial_index = [{'node_idx': i, 'x': node['x'], 'y': node['y']} for i, node in enumerate(graph)]
        
        # Connect nodes from different contours with jump connections, but limit the number
        for i, node_a in enumerate(graph):
            # Calculate distances to all other nodes
            distances = []
            for j, entry in enumerate(spatial_index):
                if j != i:
                    node_b = graph[entry['node_idx']]
                    distance = math.hypot(node_a['x'] - node_b['x'], node_a['y'] - node_b['y'])
                    distances.append({'node_idx': entry['node_idx'], 'distance': distance})
            
            # Sort by distance
            distances.sort(key=lambda x: x['distance'])
            
            # Connect to closest MAX_JUMP_CONNECTIONS nodes
            for connection in distances[:MAX_JUMP_CONNECTIONS]:
                node_b_idx = connection['node_idx']
                node_b = graph[node_b_idx]
                
                # Check if connection already exists
                if not any(n.get('node_idx') == node_b_idx for n in node_a['neighbors']):
                    node_a['neighbors'].append({
                        'node_idx': node_b_idx,
                        'is_jump': True,
                        'jump_distance': connection['distance']
                    })
                
                if not any(n.get('node_idx') == i for n in node_b['neighbors']):
                    node_b['neighbors'].append({
                        'node_idx': i,
                        'is_jump': True,
                        'jump_distance': connection['distance']
                    })
        
        return graph, node_map
    
    def add_start_end_to_graph(self, graph, node_map, start, end):
        """Add start and end points to the graph for path finding"""
        MAX_CONNECTIONS = 10  # Limit the number of connections from start/end points
        
        # Check if start and end points already exist in the graph
        start_key = f"{start['x']},{start['y']}"
        end_key = f"{end['x']},{end['y']}"
        
        start_idx = node_map.get(start_key, len(graph))
        end_idx = node_map.get(end_key, len(graph) + (1 if start_idx == len(graph) else 0))
        
        # Add start point if it doesn't exist
        if start_key not in node_map:
            start_node = {'x': start['x'], 'y': start['y'], 'neighbors': []}
            graph.append(start_node)
            node_map[start_key] = start_idx
        
        # Add end point if it doesn't exist
        if end_key not in node_map:
            end_node = {'x': end['x'], 'y': end['y'], 'neighbors': []}
            graph.append(end_node)
            node_map[end_key] = end_idx
        
        # Find the closest nodes to connect to start and end
        start_node = graph[start_idx]
        end_node = graph[end_idx]
        
        # Calculate distances from start to all other nodes
        start_distances = []
        for idx, node in enumerate(graph):
            if idx != start_idx:
                distance = math.hypot(start['x'] - node['x'], start['y'] - node['y'])
                start_distances.append({'node_idx': idx, 'distance': distance})
        
        # Sort by distance and connect only to the closest MAX_CONNECTIONS nodes
        start_distances.sort(key=lambda x: x['distance'])
        for connection in start_distances[:MAX_CONNECTIONS]:
            node_idx = connection['node_idx']
            node = graph[node_idx]
            distance = connection['distance']
            
            start_node['neighbors'].append({
                'node_idx': node_idx,
                'is_jump': True,
                'jump_distance': distance
            })
            
            node['neighbors'].append({
                'node_idx': start_idx,
                'is_jump': True,
                'jump_distance': distance
            })
        
        # Calculate distances from end to all other nodes
        end_distances = []
        for idx, node in enumerate(graph):
            if idx != end_idx:
                distance = math.hypot(end['x'] - node['x'], end['y'] - node['y'])
                end_distances.append({'node_idx': idx, 'distance': distance})
        
        # Sort by distance and connect only to the closest MAX_CONNECTIONS nodes
        end_distances.sort(key=lambda x: x['distance'])
        for connection in end_distances[:MAX_CONNECTIONS]:
            node_idx = connection['node_idx']
            node = graph[node_idx]
            distance = connection['distance']
            
            end_node['neighbors'].append({
                'node_idx': node_idx,
                'is_jump': True,
                'jump_distance': distance
            })
            
            node['neighbors'].append({
                'node_idx': end_idx,
                'is_jump': True,
                'jump_distance': distance
            })
        
        return start_idx, end_idx
    
    def dijkstra_with_minimal_jumps(self, graph, start_idx, end_idx):
        """Dijkstra algorithm that minimizes jump distances"""
        distances = [float('inf')] * len(graph)
        previous = [None] * len(graph)
        total_jump_distances = [float('inf')] * len(graph)
        
        priority_queue = PriorityQueue()
        
        distances[start_idx] = 0
        total_jump_distances[start_idx] = 0
        priority_queue.put((0, start_idx))
        
        while not priority_queue.empty():
            _, min_distance_node = priority_queue.get()
            
            if min_distance_node == end_idx:
                break
            
            current_node = graph[min_distance_node]
            for neighbor in current_node['neighbors']:
                neighbor_idx = neighbor['node_idx']
                neighbor_node = graph[neighbor_idx]
                
                jump_distance = neighbor.get('jump_distance', 0) if neighbor.get('is_jump', False) else 0
                distance = math.hypot(
                    current_node['x'] - neighbor_node['x'],
                    current_node['y'] - neighbor_node['y']
                )
                alt = distances[min_distance_node] + distance
                total_jump_dist = total_jump_distances[min_distance_node] + jump_distance
                
                if (total_jump_dist < total_jump_distances[neighbor_idx] or
                   (total_jump_dist == total_jump_distances[neighbor_idx] and alt < distances[neighbor_idx])):
                    distances[neighbor_idx] = alt
                    previous[neighbor_idx] = min_distance_node
                    total_jump_distances[neighbor_idx] = total_jump_dist
                    priority_queue.put((total_jump_dist, neighbor_idx))
        
        path = []
        u = end_idx
        
        while u is not None:
            path.insert(0, {'x': graph[u]['x'], 'y': graph[u]['y']})
            u = previous[u]
        
        return path
    
    def find_path_with_minimal_jump_distances(self, contours, start, end):
        """Find a path between two points with minimal jumps"""
        graph, node_map = self.create_graph_with_connection_types(contours)
        start_idx, end_idx = self.add_start_end_to_graph(graph, node_map, start, end)
        path = self.dijkstra_with_minimal_jumps(graph, start_idx, end_idx)
        return path
    
    def trace_contours(self, ordered_contours, is_loop=False, minimize_jumps=True):
        """Trace contours and add connecting paths if needed"""
        result = []
        paths_used = ordered_contours.copy()
        
        for i in range(len(ordered_contours) - (0 if is_loop else 1)):
            current_contour = ordered_contours[i]
            
            # If looping, add 1st contour again
            next_contour = ordered_contours[(i + 1) % len(ordered_contours)]
            start = current_contour[-1]  # End of the current contour
            end = next_contour[0]  # Start of the next contour
            
            path = []
            if minimize_jumps:
                # Find path between contours
                path = self.find_path_with_minimal_jump_distances(paths_used, start, end)
            
            result.append(current_contour)
            if path:  # Add the path only if it has points
                result.append(path)
                paths_used.append(path)  # Add the used path to the list of paths
        
        # If not looping, add the last contour as it doesn't need a connecting path
        if not is_loop:
            result.append(ordered_contours[-1])
        
        return result
    
    def remove_consecutive_duplicates(self, points):
        """Remove consecutive duplicate points"""
        if not points:
            return points
        
        result = [points[0]]
        for i in range(1, len(points)):
            prev_point = points[i-1]
            curr_point = points[i]
            if prev_point['x'] != curr_point['x'] or prev_point['y'] != curr_point['y']:
                result.append(curr_point)
        
        return result
    
    def find_maximal_center(self, points):
        """Find the center of the bounding box of the points"""
        if not points:
            return {'centerX': 0, 'centerY': 0, 'width': 0, 'height': 0}
        
        min_x = min(p['x'] for p in points)
        max_x = max(p['x'] for p in points)
        min_y = min(p['y'] for p in points)
        max_y = max(p['y'] for p in points)
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        width = max_x - min_x
        height = max_y - min_y
        
        return {'centerX': center_x, 'centerY': center_y, 'width': width, 'height': height}
    
    def calculate_centroid(self, points):
        """Calculate the centroid (average point) of a set of points"""
        if not points:
            return {'x': 0, 'y': 0}
        
        sum_x = sum(p['x'] for p in points)
        sum_y = sum(p['y'] for p in points)
        
        return {'x': sum_x / len(points), 'y': sum_y / len(points)}
    
    def reorder_points_for_loop(self, points, start_near=None):
        """Reorder points to start near a specified point or the centroid"""
        if not points:
            return points
        
        if start_near is None:
            start_near = self.calculate_centroid(points)
        
        min_dist = float('inf')
        start_index = 0
        
        # Find the point nearest to the specified point or centroid
        for i, point in enumerate(points):
            dist = math.hypot(point['x'] - start_near['x'], point['y'] - start_near['y'])
            if dist < min_dist:
                min_dist = dist
                start_index = i
        
        # Reorder points to start from the closest point
        reordered = points[start_index:] + points[:start_index+1]
        return self.remove_consecutive_duplicates(reordered) 